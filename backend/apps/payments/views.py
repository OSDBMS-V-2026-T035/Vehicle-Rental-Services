"""Server-side Razorpay order creation and payment verification."""

import json
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.bookings.models import Booking
from apps.bookings.services import expire_checkout_holds
from apps.notifications.services import notify_paid_booking_with_documents
from .models import PaymentTransaction


def _payload(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}


def _customer_only(view):
    @login_required
    def wrapped(request, *args, **kwargs):
        if request.user.role != User.Role.USER:
            return JsonResponse({"ok": False, "message": "Customer access only."}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


def _razorpay_client():
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        return None
    import razorpay
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def _amount_in_paise(amount):
    return int((Decimal(amount) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _order_response(payment, order):
    """Build the single checkout contract used for both new and retried orders."""
    return {
        "ok": True, "key_id": settings.RAZORPAY_KEY_ID, "order_id": order["id"],
        "amount": _amount_in_paise(payment.amount), "currency": payment.currency,
        "payment_id": payment.id, "description": f"RideHub booking #{payment.booking_id}",
        "test_mode": settings.RAZORPAY_KEY_ID.startswith("rzp_test_"),
        "prefill": {"name": payment.customer.get_full_name(), "email": payment.customer.email, "contact": f"+91{payment.customer.phone_number}"},
    }


def _provider_payment_matches(payment, provider_payment):
    """Ensure a fetched Razorpay payment belongs to this exact server order."""
    return (str(provider_payment.get("order_id") or "") == payment.provider_reference
            and int(provider_payment.get("amount") or 0) == _amount_in_paise(payment.amount)
            and str(provider_payment.get("currency") or "").upper() == payment.currency.upper())


def _capture_and_record(client, payment, gateway_payment_id):
    """Capture an authorised payment before marking a booking as paid."""
    provider_payment = client.payment.fetch(gateway_payment_id)
    if not _provider_payment_matches(payment, provider_payment):
        raise ValueError("Provider payment does not match this reservation.")
    if provider_payment.get("status") == "authorized":
        provider_payment = client.payment.capture(gateway_payment_id, _amount_in_paise(payment.amount), {"currency": payment.currency})
    if provider_payment.get("status") != "captured":
        raise ValueError("Payment is still awaiting bank confirmation.")
    payment.status = PaymentTransaction.Status.PAID
    payment.provider_payment_id = gateway_payment_id
    payment.save(update_fields=["status", "provider_payment_id", "updated_at"])


def _latest_provider_payment(client, payment):
    """Find a captured/authorised provider payment for a preserved order."""
    result = client.payment.all({"order_id": payment.provider_reference, "count": 100})
    for provider_payment in reversed(result.get("items", [])):
        if provider_payment.get("status") in {"captured", "authorized"} and _provider_payment_matches(payment, provider_payment):
            return str(provider_payment.get("id") or "")
    return ""


def _notify_customer_of_paid_booking(payment):
    """Send the customer their receipt and ticket; no shopkeeper notification."""
    notify_paid_booking_with_documents(payment)


def _confirm_paid_booking(payment):
    """A captured payment is the booking confirmation; shops do not approve it."""
    booking = payment.booking
    if booking.status == Booking.Status.PENDING:
        booking.status = Booking.Status.CONFIRMED
        booking.save(update_fields=["status", "updated_at"])


def _payment_window_message(payment):
    deadline = payment.booking.payment_expires_at
    if deadline and deadline <= timezone.now():
        return "Your 10-minute payment window has expired. The vehicle is free again; please search and try booking again."
    return "This booking is no longer awaiting payment."


@_customer_only
@require_POST
def create_razorpay_order(request, payment_id):
    client = _razorpay_client()
    if client is None:
        return JsonResponse({"ok": False, "message": "Razorpay is not configured yet. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to .env, then restart the service."}, status=503)
    try:
        expire_checkout_holds()
        with transaction.atomic():
            payment = PaymentTransaction.objects.select_for_update().select_related("booking", "booking__vehicle", "customer").get(pk=payment_id, customer=request.user)
            if payment.booking.status != Booking.Status.PENDING:
                return JsonResponse({"ok": False, "message": _payment_window_message(payment)}, status=409)
            if payment.status == PaymentTransaction.Status.PAID:
                return JsonResponse({"ok": False, "message": "This payment has already been received."}, status=409)
            if payment.status != PaymentTransaction.Status.PENDING:
                return JsonResponse({"ok": False, "message": "This payment cannot be completed in its current state."}, status=409)
            amount = _amount_in_paise(payment.amount)
            order = None
            if payment.provider == "RAZORPAY" and payment.provider_reference:
                existing = client.order.fetch(payment.provider_reference)
                if (existing.get("id") == payment.provider_reference and int(existing.get("amount") or 0) == amount
                        and str(existing.get("currency") or "").upper() == payment.currency.upper()
                        and existing.get("status") in {"created", "attempted"}):
                    order = existing
            if order is None:
                order = client.order.create(data={"amount": amount, "currency": payment.currency, "receipt": f"ridehub-pay-{payment.id}"[:40], "notes": {"payment_id": str(payment.id), "booking_id": str(payment.booking_id)}})
                payment.provider = "RAZORPAY"
                payment.provider_reference = order["id"]
                payment.save(update_fields=["provider", "provider_reference", "updated_at"])
    except PaymentTransaction.DoesNotExist:
        return JsonResponse({"ok": False, "message": "Payment record not found."}, status=404)
    except Exception:
        return JsonResponse({"ok": False, "message": "Unable to start secure checkout. Please try again shortly."}, status=502)
    return JsonResponse(_order_response(payment, order))


@_customer_only
@require_POST
def verify_razorpay_payment(request):
    client = _razorpay_client()
    if client is None:
        return JsonResponse({"ok": False, "message": "Razorpay is not configured yet."}, status=503)
    payload = _payload(request)
    try:
        payment_id = int(payload.get("payment_id"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "message": "Invalid payment confirmation."}, status=400)
    order_id, gateway_payment_id, signature = (str(payload.get(key) or "") for key in ("razorpay_order_id", "razorpay_payment_id", "razorpay_signature"))
    if not order_id or not gateway_payment_id or not signature:
        return JsonResponse({"ok": False, "message": "Incomplete payment confirmation."}, status=400)
    try:
        expire_checkout_holds()
        with transaction.atomic():
            payment = PaymentTransaction.objects.select_for_update().select_related("booking", "booking__vehicle", "customer").get(pk=payment_id, customer=request.user)
            if payment.booking.status != Booking.Status.PENDING:
                return JsonResponse({"ok": False, "message": _payment_window_message(payment)}, status=409)
            if payment.status == PaymentTransaction.Status.PAID:
                if payment.provider_payment_id == gateway_payment_id:
                    return JsonResponse({"ok": True, "message": "Payment was already verified."})
                return JsonResponse({"ok": False, "message": "This payment was already completed."}, status=409)
            if payment.status != PaymentTransaction.Status.PENDING or payment.provider != "RAZORPAY" or payment.provider_reference != order_id:
                return JsonResponse({"ok": False, "message": "This checkout session is no longer valid. Start payment again."}, status=409)
            client.utility.verify_payment_signature({"razorpay_order_id": order_id, "razorpay_payment_id": gateway_payment_id, "razorpay_signature": signature})
            _capture_and_record(client, payment, gateway_payment_id)
    except PaymentTransaction.DoesNotExist:
        return JsonResponse({"ok": False, "message": "Payment record not found."}, status=404)
    except Exception:
        return JsonResponse({"ok": False, "message": "We could not verify this payment. No booking status was changed."}, status=400)
    _confirm_paid_booking(payment)
    _notify_customer_of_paid_booking(payment)
    return JsonResponse({"ok": True, "message": "Payment verified successfully. Your ride is confirmed."})


@_customer_only
@require_POST
def reconcile_razorpay_payment(request, payment_id):
    """Recover a captured/authorised payment when the checkout callback is lost."""
    client = _razorpay_client()
    if client is None:
        return JsonResponse({"ok": False, "message": "Razorpay is not configured yet."}, status=503)
    try:
        expire_checkout_holds()
        with transaction.atomic():
            payment = PaymentTransaction.objects.select_for_update().select_related("booking", "booking__vehicle", "customer").get(pk=payment_id, customer=request.user)
            if payment.status == PaymentTransaction.Status.PAID:
                return JsonResponse({"ok": True, "status": "PAID", "message": "Payment was already confirmed."})
            if payment.booking.status != Booking.Status.PENDING:
                return JsonResponse({"ok": True, "status": "EXPIRED", "message": _payment_window_message(payment)})
            if payment.status != PaymentTransaction.Status.PENDING or payment.provider != "RAZORPAY" or not payment.provider_reference:
                return JsonResponse({"ok": True, "status": "PENDING", "message": "Payment is still available to retry."})
            gateway_payment_id = _latest_provider_payment(client, payment)
            if not gateway_payment_id:
                return JsonResponse({"ok": True, "status": "PENDING", "message": "No completed payment was found yet. You can safely retry."})
            _capture_and_record(client, payment, gateway_payment_id)
    except PaymentTransaction.DoesNotExist:
        return JsonResponse({"ok": False, "message": "Payment record not found."}, status=404)
    except Exception:
        return JsonResponse({"ok": True, "status": "PENDING", "message": "Payment confirmation is still in progress. Do not make a duplicate payment."})
    _confirm_paid_booking(payment)
    _notify_customer_of_paid_booking(payment)
    return JsonResponse({"ok": True, "status": "PAID", "message": "Payment confirmed successfully."})


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    """Reconcile captured Razorpay payments when the customer has left checkout."""
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        return JsonResponse({"ok": False}, status=503)
    signature = request.headers.get("X-Razorpay-Signature", "")
    try:
        client = _razorpay_client()
        if client is None or not signature:
            raise ValueError("Missing Razorpay configuration or signature")
        client.utility.verify_webhook_signature(request.body.decode("utf-8"), signature, settings.RAZORPAY_WEBHOOK_SECRET)
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False}, status=400)

    if payload.get("event") != "payment.captured":
        return JsonResponse({"ok": True})
    entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = str(entity.get("order_id") or "")
    gateway_payment_id = str(entity.get("id") or "")
    amount = entity.get("amount")
    if not order_id or not gateway_payment_id:
        return JsonResponse({"ok": True})
    expire_checkout_holds()
    with transaction.atomic():
        payment = PaymentTransaction.objects.select_for_update().select_related("booking", "booking__vehicle", "customer").filter(
            provider="RAZORPAY", provider_reference=order_id
        ).first()
        if payment is None or payment.booking.status != Booking.Status.PENDING or payment.status == PaymentTransaction.Status.PAID or amount != _amount_in_paise(payment.amount):
            return JsonResponse({"ok": True})
        if payment.status != PaymentTransaction.Status.PENDING:
            return JsonResponse({"ok": True})
        try:
            _capture_and_record(client, payment, gateway_payment_id)
        except Exception:
            return JsonResponse({"ok": True})
    _confirm_paid_booking(payment)
    _notify_customer_of_paid_booking(payment)
    return JsonResponse({"ok": True})

