"""Server-side Razorpay order creation and payment verification."""

import json
import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.bookings.models import Booking, BookingChange, BookingRefund
from apps.bookings.lifecycle import apply_paid_extension, prepare_extension
from apps.bookings.services import expire_checkout_holds
from apps.bookings.finance import snapshot_booking_financials
from apps.notifications.services import notify_paid_booking_with_documents
from .gateways import get_payment_gateway
from .models import PaymentTransaction


logger = logging.getLogger(__name__)


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


def _payment_gateway(provider=None):
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        return None
    return get_payment_gateway(provider)


def _razorpay_configuration_error(require_webhook=False):
    """Return a customer-safe configuration error without exposing secrets."""
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        return "Razorpay test keys are not configured on the server yet."
    if not settings.RAZORPAY_KEY_ID.startswith(("rzp_test_", "rzp_live_")):
        return "The Razorpay Key ID on the server is invalid. Use a Test Mode or Live Mode Key ID."
    if require_webhook and not settings.RAZORPAY_WEBHOOK_SECRET:
        return "Razorpay webhook signing secret is not configured on the server yet."
    return ""


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


def _extension_order_response(change, order):
    return {
        "ok": True, "key_id": settings.RAZORPAY_KEY_ID, "order_id": order["id"],
        "amount": _amount_in_paise(change.amount), "currency": change.currency,
        "change_id": change.id, "booking_id": change.booking_id,
        "to_return": change.to_return.isoformat() if change.to_return else None,
        "description": f"RideHub booking #{change.booking_id} extension",
        "test_mode": settings.RAZORPAY_KEY_ID.startswith("rzp_test_"),
        "prefill": {
            "name": change.requested_by.get_full_name(),
            "email": change.requested_by.email,
            "contact": f"+91{change.requested_by.phone_number}",
        },
        "expires_at": change.expires_at.isoformat() if change.expires_at else None,
    }


def _extension_payment_matches(change, provider_payment):
    return (
        str(provider_payment.get("order_id") or "") == change.provider_order_id
        and int(provider_payment.get("amount") or 0) == _amount_in_paise(change.amount)
        and str(provider_payment.get("currency") or "").upper() == change.currency.upper()
    )


def _capture_extension_payment(gateway, change, gateway_payment_id):
    provider_payment = gateway.fetch_payment(gateway_payment_id)
    if not _extension_payment_matches(change, provider_payment):
        raise ValueError("Provider payment does not match this extension.")
    if provider_payment.get("status") == "authorized":
        provider_payment = gateway.capture_payment(
            gateway_payment_id, _amount_in_paise(change.amount), {"currency": change.currency},
        )
    if provider_payment.get("status") != "captured":
        raise ValueError("Extension payment is still awaiting bank confirmation.")


def _refund_receipt(change_id, source):
    import hashlib
    digest = hashlib.sha256(f"ridehub-refund:{change_id}:{source}".encode("utf-8")).hexdigest()[:28]
    return f"RH-RF-{digest}"


def _refund_unapplied_extension(
    gateway, change, gateway_payment_id, *, reason="Extension date hold expired",
    terminal_status=BookingChange.Status.EXPIRED,
):
    """Refund a captured add-on that cannot be safely applied to the booking."""
    source = f"unapplied:{gateway_payment_id}"
    with transaction.atomic():
        refund, _ = BookingRefund.objects.get_or_create(
            change=change, source_key=source,
            defaults={
                "provider_payment_id": gateway_payment_id, "amount": change.amount,
                "receipt": _refund_receipt(change.id, source),
            },
        )
        if refund.status == BookingRefund.Status.INITIATED:
            return True
        try:
            result = None
            if refund.status == BookingRefund.Status.FAILED:
                listed = gateway.list_refunds(gateway_payment_id)
                result = next((item for item in listed.get("items", []) if str(item.get("receipt") or "") == refund.receipt), None)
                if result and str(result.get("status") or "").lower() == "failed":
                    refund.receipt = f"RH-RF-{uuid.uuid4().hex[:20]}"
                    refund.status = BookingRefund.Status.PENDING
                    refund.provider_status = "failed"
                    refund.error_message = "Retrying after the provider marked the previous refund failed."
                    refund.save(update_fields=["receipt", "status", "provider_status", "error_message", "updated_at"])
                    result = None
            if result is None:
                result = gateway.refund(gateway_payment_id, {
                    "amount": _amount_in_paise(change.amount), "receipt": refund.receipt,
                    "notes": {"booking_id": str(change.booking_id), "reason": reason[:200]},
                })
            if str(result.get("payment_id") or gateway_payment_id) != gateway_payment_id or int(result.get("amount") or 0) != _amount_in_paise(change.amount):
                raise ValueError("The refund response did not match the expired extension payment.")
            if str(result.get("status") or "pending").lower() == "failed":
                refund.provider_refund_id = str(result.get("id") or "")
                refund.provider_status = "failed"
                refund.status = BookingRefund.Status.FAILED
                refund.error_message = "Razorpay marked this refund as failed. Retry to reconcile it."
                refund.save(update_fields=["provider_refund_id", "provider_status", "status", "error_message", "updated_at"])
                return False
            refund.provider_refund_id = str(result.get("id") or "")
            refund.provider_status = str(result.get("status") or "pending")
            refund.status = BookingRefund.Status.INITIATED
            refund.error_message = ""
            refund.save(update_fields=["provider_refund_id", "provider_status", "status", "error_message", "updated_at"])
            change.provider_payment_id = gateway_payment_id
            change.refunded_amount = change.amount
            change.refund_status = "INITIATED"
            change.status = terminal_status
            change.save(update_fields=["provider_payment_id", "refunded_amount", "refund_status", "status", "updated_at"])
            return True
        except Exception:
            logger.exception("Unable to refund expired extension change %s", change.id)
            refund.status = BookingRefund.Status.FAILED
            refund.error_message = "Refund could not be confirmed; retry with the same receipt."
            refund.save(update_fields=["status", "error_message", "updated_at"])
            return False


def _finalize_extension_payment(gateway, change, gateway_payment_id):
    """Apply an add-on after capture, refunding it if finalization loses its hold."""
    _capture_extension_payment(gateway, change, gateway_payment_id)
    try:
        return apply_paid_extension(change_id=change.id, provider_payment_id=gateway_payment_id)
    except Exception:
        change.refresh_from_db()
        if (change.status == BookingChange.Status.COMPLETED
                and change.provider_payment_id == gateway_payment_id):
            return change.booking
        provider_payment = gateway.fetch_payment(gateway_payment_id)
        if not (_extension_payment_matches(change, provider_payment)
                and provider_payment.get("status") == "captured"):
            raise
        reason = "Extension could not be finalized after payment capture"
        if not _refund_unapplied_extension(
            gateway, change, gateway_payment_id, reason=reason,
            terminal_status=BookingChange.Status.FAILED,
        ):
            raise RuntimeError("Payment was captured but the extension could not be applied; refund reconciliation is required.")
        raise ValueError("Payment was captured, but the extension could not be applied. A refund has been initiated.")


def _provider_payment_matches(payment, provider_payment):
    """Ensure a fetched Razorpay payment belongs to this exact server order."""
    return (str(provider_payment.get("order_id") or "") == payment.provider_reference
            and int(provider_payment.get("amount") or 0) == _amount_in_paise(payment.amount)
            and str(provider_payment.get("currency") or "").upper() == payment.currency.upper())


def _capture_and_record(gateway, payment, gateway_payment_id):
    """Capture an authorised payment before marking a booking as paid."""
    provider_payment = gateway.fetch_payment(gateway_payment_id)
    if not _provider_payment_matches(payment, provider_payment):
        raise ValueError("Provider payment does not match this reservation.")
    if provider_payment.get("status") == "authorized":
        provider_payment = gateway.capture_payment(gateway_payment_id, _amount_in_paise(payment.amount), {"currency": payment.currency})
    if provider_payment.get("status") != "captured":
        raise ValueError("Payment is still awaiting bank confirmation.")
    payment.status = PaymentTransaction.Status.PAID
    payment.provider_payment_id = gateway_payment_id
    payment.save(update_fields=["status", "provider_payment_id", "updated_at"])


def _latest_provider_payment(gateway, payment):
    """Find a captured/authorised provider payment for a preserved order."""
    result = gateway.list_payments(payment.provider_reference, count=100)
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
    # Must stay inside the caller's transaction when this is reached from a
    # verification/webhook path, so duplicate callbacks retain one snapshot.
    snapshot_booking_financials(booking)


def _payment_window_message(payment):
    deadline = payment.booking.payment_expires_at
    if deadline and deadline <= timezone.now():
        return "Your 10-minute payment window has expired. The vehicle is free again; please search and try booking again."
    return "This booking is no longer awaiting payment."


@_customer_only
def razorpay_checkout_status(request):
    """Preflight configuration before opening the third-party checkout UI."""
    error = _razorpay_configuration_error(require_webhook=True)
    if error:
        return JsonResponse({"ok": False, "message": error}, status=503)
    return JsonResponse({
        "ok": True,
        "test_mode": settings.RAZORPAY_KEY_ID.startswith("rzp_test_"),
        "message": "Razorpay checkout and webhook recovery are configured.",
    })


@_customer_only
@require_POST
def create_razorpay_order(request, payment_id):
    configuration_error = _razorpay_configuration_error()
    if configuration_error:
        return JsonResponse({"ok": False, "message": configuration_error}, status=503)
    gateway = _payment_gateway()
    if gateway is None:
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
                existing = gateway.fetch_order(payment.provider_reference)
                if (existing.get("id") == payment.provider_reference and int(existing.get("amount") or 0) == amount
                        and str(existing.get("currency") or "").upper() == payment.currency.upper()
                        and existing.get("status") in {"created", "attempted"}):
                    order = existing
            if order is None:
                order = gateway.create_order({"amount": amount, "currency": payment.currency, "receipt": f"ridehub-pay-{payment.id}"[:40], "notes": {"payment_id": str(payment.id), "booking_id": str(payment.booking_id)}})
                payment.provider = "RAZORPAY"
                payment.provider_reference = order["id"]
                payment.save(update_fields=["provider", "provider_reference", "updated_at"])
    except PaymentTransaction.DoesNotExist:
        return JsonResponse({"ok": False, "message": "Payment record not found."}, status=404)
    except Exception:
        logger.exception("Unable to create Razorpay order for payment %s", payment_id)
        return JsonResponse({"ok": False, "message": "Unable to start secure checkout. Please try again shortly."}, status=502)
    return JsonResponse(_order_response(payment, order))


@_customer_only
@require_POST
def verify_razorpay_payment(request):
    gateway = _payment_gateway("RAZORPAY")
    if gateway is None:
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
            gateway.verify_payment_signature({"razorpay_order_id": order_id, "razorpay_payment_id": gateway_payment_id, "razorpay_signature": signature})
            _capture_and_record(gateway, payment, gateway_payment_id)
            _confirm_paid_booking(payment)
    except PaymentTransaction.DoesNotExist:
        return JsonResponse({"ok": False, "message": "Payment record not found."}, status=404)
    except Exception:
        return JsonResponse({"ok": False, "message": "We could not verify this payment. No booking status was changed."}, status=400)
    _notify_customer_of_paid_booking(payment)
    return JsonResponse({"ok": True, "message": "Payment verified successfully. Your ride is confirmed."})


@_customer_only
@require_POST
def reconcile_razorpay_payment(request, payment_id):
    """Recover a captured/authorised payment when the checkout callback is lost."""
    gateway = _payment_gateway("RAZORPAY")
    if gateway is None:
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
            gateway_payment_id = _latest_provider_payment(gateway, payment)
            if not gateway_payment_id:
                return JsonResponse({"ok": True, "status": "PENDING", "message": "No completed payment was found yet. You can safely retry."})
            _capture_and_record(gateway, payment, gateway_payment_id)
            _confirm_paid_booking(payment)
    except PaymentTransaction.DoesNotExist:
        return JsonResponse({"ok": False, "message": "Payment record not found."}, status=404)
    except Exception:
        return JsonResponse({"ok": True, "status": "PENDING", "message": "Payment confirmation is still in progress. Do not make a duplicate payment."})
    _notify_customer_of_paid_booking(payment)
    return JsonResponse({"ok": True, "status": "PAID", "message": "Payment confirmed successfully."})


@_customer_only
@require_POST
@transaction.atomic
def create_extension_order(request, booking_id):
    configuration_error = _razorpay_configuration_error()
    if configuration_error:
        return JsonResponse({"ok": False, "message": configuration_error}, status=503)
    gateway = _payment_gateway("RAZORPAY")
    if gateway is None:
        return JsonResponse({"ok": False, "message": "Razorpay is not configured yet."}, status=503)
    new_return = parse_date(str(_payload(request).get("return_date") or ""))
    if not new_return:
        return JsonResponse({"ok": False, "message": "Choose a valid new return date."}, status=400)
    expire_checkout_holds()
    change = None
    try:
        change = BookingChange.objects.filter(
            booking_id=booking_id, requested_by=request.user, kind=BookingChange.Kind.EXTEND,
            status=BookingChange.Status.PENDING_PAYMENT, to_return=new_return,
            expires_at__gt=timezone.now(),
        ).select_related("booking", "requested_by").select_for_update().first()
        if change:
            booking = change.booking
            order = None
            if change.provider_order_id:
                existing_order = gateway.fetch_order(change.provider_order_id)
                if (existing_order.get("id") == change.provider_order_id
                        and int(existing_order.get("amount") or 0) == _amount_in_paise(change.amount)
                        and str(existing_order.get("currency") or "").upper() == change.currency.upper()
                        and existing_order.get("status") in {"created", "attempted"}):
                    order = existing_order
            if order is None:
                # The old provider order may already have a captured payment;
                # reconcile it before issuing another order for this change.
                if change.provider_order_id:
                    payments = gateway.list_payments(change.provider_order_id, count=100)
                    captured = next((item for item in reversed(payments.get("items", []))
                                     if item.get("status") in {"authorized", "captured"}
                                     and _extension_payment_matches(change, item)), None)
                    if captured:
                        return JsonResponse({"ok": False, "message": "An extension payment was already found. Refresh your booking history before trying again."}, status=409)
                order = gateway.create_order({
                    "amount": _amount_in_paise(change.amount), "currency": change.currency,
                    "receipt": f"ridehub-ext-{change.id}-{uuid.uuid4().hex[:12]}",
                    "notes": {"booking_id": str(booking.id), "change_id": str(change.id), "kind": "booking_extension"},
                })
        else:
            booking, change = prepare_extension(customer=request.user, booking_id=booking_id, new_return=new_return)
            order = gateway.create_order({
                "amount": _amount_in_paise(change.amount), "currency": change.currency,
                "receipt": f"ridehub-ext-{change.id}-{uuid.uuid4().hex[:12]}",
                "notes": {"booking_id": str(booking.id), "change_id": str(change.id), "kind": "booking_extension"},
            })
        if not order.get("id"):
            raise RuntimeError("Razorpay did not return an extension order reference.")
        change.provider_order_id = str(order["id"])
        change.save(update_fields=["provider_order_id", "updated_at"])
    except LookupError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=404)
    except ValueError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=409)
    except Exception:
        logger.exception("Unable to create Razorpay extension order for booking %s", booking_id)
        if change:
            # Keep a persisted provider order pending on transient lookup
            # errors: it may still be usable by an open checkout. Only close
            # a brand-new hold when no provider order was ever saved.
            BookingChange.objects.filter(
                pk=change.pk, provider_order_id="", status=BookingChange.Status.PENDING_PAYMENT,
            ).update(
                status=BookingChange.Status.FAILED, updated_at=timezone.now(),
            )
        return JsonResponse({"ok": False, "message": "Unable to start the extension payment. Please retry."}, status=502)
    return JsonResponse(_extension_order_response(change, order))


@_customer_only
@require_POST
def verify_extension_payment(request):
    gateway = _payment_gateway("RAZORPAY")
    if gateway is None:
        return JsonResponse({"ok": False, "message": "Razorpay is not configured yet."}, status=503)
    payload = _payload(request)
    try:
        change_id = int(payload.get("change_id"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "message": "Invalid extension payment confirmation."}, status=400)
    order_id, gateway_payment_id, signature = (
        str(payload.get(key) or "") for key in
        ("razorpay_order_id", "razorpay_payment_id", "razorpay_signature")
    )
    if not order_id or not gateway_payment_id or not signature:
        return JsonResponse({"ok": False, "message": "Incomplete extension payment confirmation."}, status=400)
    try:
        expire_checkout_holds()
        change = BookingChange.objects.select_related("booking", "requested_by").get(
            pk=change_id, booking__customer=request.user, kind=BookingChange.Kind.EXTEND,
        )
        if change.status == BookingChange.Status.COMPLETED and change.provider_payment_id == gateway_payment_id:
            return JsonResponse({"ok": True, "message": "Extension payment was already verified."})
        if change.provider_order_id != order_id:
            return JsonResponse({"ok": False, "message": "This extension checkout does not match the booking."}, status=409)
        gateway.verify_payment_signature({
            "razorpay_order_id": order_id, "razorpay_payment_id": gateway_payment_id,
            "razorpay_signature": signature,
        })
        if change.status == BookingChange.Status.EXPIRED or (change.expires_at and change.expires_at <= timezone.now()):
            provider_payment = gateway.fetch_payment(gateway_payment_id)
            if _extension_payment_matches(change, provider_payment) and provider_payment.get("status") == "captured":
                if not _refund_unapplied_extension(gateway, change, gateway_payment_id):
                    return JsonResponse({"ok": False, "message": "Payment arrived after the date hold expired. Refund retry is needed; please contact support."}, status=502)
            return JsonResponse({"ok": False, "message": "The extension date hold expired. Any captured payment has been refunded."}, status=409)
        if change.status != BookingChange.Status.PENDING_PAYMENT:
            return JsonResponse({"ok": False, "message": "This extension checkout is no longer active."}, status=409)
        booking = _finalize_extension_payment(gateway, change, gateway_payment_id)
    except BookingChange.DoesNotExist:
        return JsonResponse({"ok": False, "message": "Extension request not found."}, status=404)
    except Exception as exc:
        logger.exception("Unable to verify extension payment %s", change_id)
        message = str(exc) if isinstance(exc, ValueError) else "We could not verify this extension payment. No booking dates were changed."
        return JsonResponse({"ok": False, "message": message}, status=400)
    return JsonResponse({"ok": True, "message": "Extension paid and confirmed.", "booking_id": booking.id, "return_date": booking.return_date.isoformat()})


@_customer_only
@require_POST
def reconcile_extension_payment(request, change_id):
    gateway = _payment_gateway("RAZORPAY")
    if gateway is None:
        return JsonResponse({"ok": False, "message": "Razorpay is not configured yet."}, status=503)
    try:
        expire_checkout_holds()
        change = BookingChange.objects.get(pk=change_id, booking__customer=request.user, kind=BookingChange.Kind.EXTEND)
    except BookingChange.DoesNotExist:
        return JsonResponse({"ok": False, "message": "Extension request not found."}, status=404)
    if change.status == BookingChange.Status.COMPLETED:
        return JsonResponse({"ok": True, "status": "PAID", "booking_id": change.booking_id})
    if change.status not in {BookingChange.Status.PENDING_PAYMENT, BookingChange.Status.EXPIRED} or not change.provider_order_id:
        return JsonResponse({"ok": True, "status": change.status})
    try:
        result = gateway.list_payments(change.provider_order_id, count=100)
        matched = next((item for item in reversed(result.get("items", []))
                        if item.get("status") in {"authorized", "captured"}
                        and _extension_payment_matches(change, item)), None)
        if not matched:
            return JsonResponse({"ok": True, "status": "PENDING", "message": "No completed extension payment was found yet."})
        payment_id = str(matched["id"])
        expired = change.status == BookingChange.Status.EXPIRED or bool(change.expires_at and change.expires_at <= timezone.now())
        if expired:
            if matched.get("status") == "captured" and _refund_unapplied_extension(gateway, change, payment_id):
                return JsonResponse({"ok": True, "status": "EXPIRED", "message": "The extension date hold expired; a refund was initiated."})
            return JsonResponse({"ok": True, "status": "EXPIRED", "message": "The extension date hold expired. Contact support to reconcile payment."})
        booking = _finalize_extension_payment(gateway, change, payment_id)
        return JsonResponse({"ok": True, "status": "PAID", "booking_id": booking.id})
    except Exception:
        logger.exception("Unable to reconcile extension change %s", change.id)
        return JsonResponse({"ok": True, "status": "PENDING", "message": "Extension payment confirmation is still in progress."})


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    """Reconcile captured Razorpay payments when the customer has left checkout."""
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        return JsonResponse({"ok": False}, status=503)
    signature = request.headers.get("X-Razorpay-Signature", "")
    try:
        gateway = _payment_gateway("RAZORPAY")
        if gateway is None or not signature:
            raise ValueError("Missing Razorpay configuration or signature")
        gateway.verify_webhook_signature(request.body.decode("utf-8"), signature, settings.RAZORPAY_WEBHOOK_SECRET)
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
        if payment is None:
            change = BookingChange.objects.select_for_update().select_related("booking", "requested_by").filter(
                provider="RAZORPAY", provider_order_id=order_id, kind=BookingChange.Kind.EXTEND,
            ).first()
            if change is None or amount != _amount_in_paise(change.amount) or not _extension_payment_matches(change, entity):
                return JsonResponse({"ok": True})
            if change.status == BookingChange.Status.EXPIRED:
                if entity.get("status") == "captured":
                    _refund_unapplied_extension(gateway, change, gateway_payment_id)
                return JsonResponse({"ok": True})
            if change.status != BookingChange.Status.PENDING_PAYMENT:
                return JsonResponse({"ok": True})
            try:
                _finalize_extension_payment(gateway, change, gateway_payment_id)
            except Exception:
                logger.exception("Unable to process captured extension webhook for change %s", change.id)
            return JsonResponse({"ok": True})
        if payment is None or payment.booking.status != Booking.Status.PENDING or payment.status == PaymentTransaction.Status.PAID or amount != _amount_in_paise(payment.amount):
            return JsonResponse({"ok": True})
        if payment.status != PaymentTransaction.Status.PENDING:
            return JsonResponse({"ok": True})
        try:
            _capture_and_record(gateway, payment, gateway_payment_id)
            _confirm_paid_booking(payment)
        except Exception:
            return JsonResponse({"ok": True})
    _notify_customer_of_paid_booking(payment)
    return JsonResponse({"ok": True})

