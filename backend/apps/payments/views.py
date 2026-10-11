"""Server-side Razorpay order creation and payment verification."""

import json
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.notifications.services import notify_user
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


@_customer_only
@require_POST
def create_razorpay_order(request, payment_id):
    client = _razorpay_client()
    if client is None:
        return JsonResponse({"ok": False, "message": "Razorpay is not configured yet. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to .env, then restart the service."}, status=503)
    try:
        with transaction.atomic():
            payment = PaymentTransaction.objects.select_for_update().select_related("booking", "booking__vehicle").get(pk=payment_id, customer=request.user)
            if payment.status == PaymentTransaction.Status.PAID:
                return JsonResponse({"ok": False, "message": "This payment has already been received."}, status=409)
            if payment.status != PaymentTransaction.Status.PENDING:
                return JsonResponse({"ok": False, "message": "This payment cannot be completed in its current state."}, status=409)
            amount = _amount_in_paise(payment.amount)
            order = client.order.create(data={"amount": amount, "currency": payment.currency, "receipt": f"ridehub-pay-{payment.id}"[:40], "notes": {"payment_id": str(payment.id), "booking_id": str(payment.booking_id)}})
            payment.provider = "RAZORPAY"
            payment.provider_reference = order["id"]
            payment.save(update_fields=["provider", "provider_reference", "updated_at"])
    except PaymentTransaction.DoesNotExist:
        return JsonResponse({"ok": False, "message": "Payment record not found."}, status=404)
    except Exception:
        return JsonResponse({"ok": False, "message": "Unable to start secure checkout. Please try again shortly."}, status=502)
    return JsonResponse({"ok": True, "key_id": settings.RAZORPAY_KEY_ID, "order_id": order["id"], "amount": amount, "currency": payment.currency, "payment_id": payment.id, "description": f"RideHub booking #{payment.booking_id}", "prefill": {"name": request.user.get_full_name(), "email": request.user.email, "contact": request.user.phone_number}})


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
        with transaction.atomic():
            payment = PaymentTransaction.objects.select_for_update().select_related("booking", "booking__vehicle").get(pk=payment_id, customer=request.user)
            if payment.status == PaymentTransaction.Status.PAID:
                if payment.provider_payment_id == gateway_payment_id:
                    return JsonResponse({"ok": True, "message": "Payment was already verified."})
                return JsonResponse({"ok": False, "message": "This payment was already completed."}, status=409)
            if payment.status != PaymentTransaction.Status.PENDING or payment.provider != "RAZORPAY" or payment.provider_reference != order_id:
                return JsonResponse({"ok": False, "message": "This checkout session is no longer valid. Start payment again."}, status=409)
            client.utility.verify_payment_signature({"razorpay_order_id": order_id, "razorpay_payment_id": gateway_payment_id, "razorpay_signature": signature})
            payment.status = PaymentTransaction.Status.PAID
            payment.provider_payment_id = gateway_payment_id
            payment.save(update_fields=["status", "provider_payment_id", "updated_at"])
    except PaymentTransaction.DoesNotExist:
        return JsonResponse({"ok": False, "message": "Payment record not found."}, status=404)
    except Exception:
        return JsonResponse({"ok": False, "message": "We could not verify this payment. No booking status was changed."}, status=400)
    notify_user(request.user, "Payment received", f"Your payment of ₹{payment.amount} for {payment.booking.vehicle.display_name} was received. The booking request is now awaiting shop confirmation.")
    notify_user(payment.booking.vehicle.shopkeeper.user, "Paid booking needs review", f"Payment of ₹{payment.amount} was verified for {payment.booking.vehicle.display_name}. Review and confirm the reservation in Reservation centre.")
    return JsonResponse({"ok": True, "message": "Payment verified successfully. Your booking is awaiting shop confirmation."})


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
    with transaction.atomic():
        payment = PaymentTransaction.objects.select_for_update().select_related("booking", "booking__vehicle", "customer").filter(
            provider="RAZORPAY", provider_reference=order_id
        ).first()
        if payment is None or payment.status == PaymentTransaction.Status.PAID or amount != _amount_in_paise(payment.amount):
            return JsonResponse({"ok": True})
        if payment.status != PaymentTransaction.Status.PENDING:
            return JsonResponse({"ok": True})
        payment.status = PaymentTransaction.Status.PAID
        payment.provider_payment_id = gateway_payment_id
        payment.save(update_fields=["status", "provider_payment_id", "updated_at"])
    notify_user(payment.customer, "Payment received", f"Your payment of ₹{payment.amount} for {payment.booking.vehicle.display_name} was received. The booking request is now awaiting shop confirmation.")
    notify_user(payment.booking.vehicle.shopkeeper.user, "Paid booking needs review", f"Payment of ₹{payment.amount} was verified for {payment.booking.vehicle.display_name}. Review and confirm the reservation in Reservation centre.")
    return JsonResponse({"ok": True})

