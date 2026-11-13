"""Audited cancellations and idempotent per-payment Razorpay refunds."""

from decimal import Decimal
import uuid

from django.db import transaction
from django.utils import timezone

from apps.adminpanel.models import AuditLog
from apps.payments.gateways import get_payment_gateway
from apps.payments.models import PaymentTransaction
from .finance import money
from .models import Booking, BookingChange, BookingRefund
from .policy import cancellation_refund_percent, refund_amount


PAID_PAYMENT_STATUSES = {
    PaymentTransaction.Status.PAID,
    PaymentTransaction.Status.PARTIALLY_REFUNDED,
}


def _refund_sources(booking):
    sources = []
    payment = PaymentTransaction.objects.select_for_update().filter(booking=booking).first()
    if payment and payment.status in PAID_PAYMENT_STATUSES:
        if not payment.provider_payment_id:
            raise ValueError("The captured payment reference is missing; support must reconcile this booking before cancellation.")
        balance = max(Decimal("0.00"), payment.amount - payment.refunded_amount)
        if balance:
            sources.append((f"payment:{payment.id}", payment.provider_payment_id, balance, payment))
    extensions = BookingChange.objects.select_for_update().filter(
        booking=booking, kind=BookingChange.Kind.EXTEND,
        status=BookingChange.Status.COMPLETED,
    )
    for extension in extensions:
        if not extension.provider_payment_id:
            raise ValueError("An extension payment reference is missing; support must reconcile this booking before cancellation.")
        balance = max(Decimal("0.00"), extension.amount - extension.refunded_amount)
        if balance:
            sources.append((f"change:{extension.id}", extension.provider_payment_id, balance, extension))
    return sources


def begin_cancellation(*, booking_id, actor, refund_percent=None, reason="", customer_request=False):
    """Persist cancellation and refund intent before any gateway request."""
    with transaction.atomic():
        try:
            booking = Booking.objects.select_for_update().select_related("vehicle").get(pk=booking_id)
        except Booking.DoesNotExist as exc:
            raise LookupError("Booking not found.") from exc
        prior = BookingChange.objects.filter(booking=booking, kind=BookingChange.Kind.CANCEL).order_by("-id").first()
        if prior:
            if prior.status in {BookingChange.Status.PROCESSING, BookingChange.Status.FAILED}:
                return prior
            if prior.status == BookingChange.Status.COMPLETED:
                return prior
        if booking.status == Booking.Status.CANCELLED:
            raise ValueError("This booking has already been cancelled.")
        if BookingChange.objects.filter(
            booking=booking, status__in=[BookingChange.Status.PENDING_PAYMENT, BookingChange.Status.PROCESSING],
        ).exclude(kind=BookingChange.Kind.CANCEL).exists():
            raise ValueError("Finish or expire the current date change before cancelling this booking.")
        payment = PaymentTransaction.objects.select_for_update().filter(booking=booking).first()
        if booking.status == Booking.Status.PENDING and (
            not payment or payment.status in {PaymentTransaction.Status.PENDING, PaymentTransaction.Status.FAILED, PaymentTransaction.Status.CANCELLED}
        ):
            booking.status = Booking.Status.CANCELLED
            booking.save(update_fields=["status", "updated_at"])
            if payment and payment.status == PaymentTransaction.Status.PENDING:
                payment.status = PaymentTransaction.Status.CANCELLED
                payment.save(update_fields=["status", "updated_at"])
            return BookingChange.objects.create(
                booking=booking, requested_by=actor, kind=BookingChange.Kind.CANCEL,
                status=BookingChange.Status.COMPLETED,
                from_pickup=booking.pickup_date, from_return=booking.return_date,
                refund_percent=0, refund_status="NOT_REQUIRED",
            )
        if customer_request:
            if booking.status != Booking.Status.CONFIRMED or booking.pickup_date < timezone.localdate():
                raise ValueError("Customer cancellation is available before pickup on confirmed bookings only.")
            if not payment or payment.status not in PAID_PAYMENT_STATUSES:
                raise ValueError("A verified paid booking is required to use this cancellation policy.")
        elif booking.status not in {Booking.Status.CONFIRMED, Booking.Status.HANDED_OVER}:
            raise ValueError("This booking cannot be cancelled at its current stage.")
        if refund_percent is None:
            refund_percent = cancellation_refund_percent(booking.pickup_date, timezone.localdate())
        if refund_percent not in {0, 50, 80, 100}:
            raise ValueError("Invalid cancellation refund tier.")
        sources = _refund_sources(booking) if payment and payment.status in PAID_PAYMENT_STATUSES else []
        if not sources:
            refund_percent = 0
        refund_rows = []
        expected_refund = Decimal("0.00")
        change = BookingChange.objects.create(
            booking=booking, requested_by=actor, kind=BookingChange.Kind.CANCEL,
            status=BookingChange.Status.PROCESSING,
            from_pickup=booking.pickup_date, from_return=booking.return_date,
            refund_percent=refund_percent, reason=" ".join(str(reason).split())[:500],
            refund_status="PROCESSING" if refund_percent else "NOT_REQUIRED",
        )
        for source_key, provider_payment_id, available_amount, source_record in sources:
            amount = refund_amount(available_amount, refund_percent)
            if amount <= 0:
                continue
            expected_refund += amount
            refund_rows.append(BookingRefund.objects.create(
                change=change, source_key=source_key, provider_payment_id=provider_payment_id,
                amount=amount, receipt=_refund_receipt(change.id, source_key),
            ))
        change.amount = expected_refund
        change.save(update_fields=["amount", "updated_at"])
        AuditLog.objects.create(
            actor=actor, action="booking_cancellation_requested", entity_type="booking", entity_id=booking.id,
            metadata={"change_id": change.id, "refund_percent": refund_percent, "expected_refund": str(expected_refund)},
        )
    return change


def _refund_receipt(change_id, source_key):
    import hashlib
    digest = hashlib.sha256(f"ridehub-cancel:{change_id}:{source_key}".encode("utf-8")).hexdigest()[:28]
    return f"RH-RF-{digest}"


def _existing_provider_refund(gateway, refund):
    """Reconcile a response lost after Razorpay accepted the refund request."""
    try:
        result = gateway.list_refunds(refund.provider_payment_id)
    except Exception:
        return None
    items = result.get("items", []) if isinstance(result, dict) else []
    return next((item for item in items if str(item.get("receipt") or "") == refund.receipt), None)


def _apply_refund_to_source(refund, change):
    amount = money(refund.amount)
    if refund.source_key.startswith("payment:"):
        payment_id = refund.source_key.split(":", 1)[1]
        payment = PaymentTransaction.objects.select_for_update().get(pk=payment_id, booking_id=change.booking_id)
        payment.refunded_amount = min(payment.amount, money(payment.refunded_amount + amount))
        payment.status = (
            PaymentTransaction.Status.REFUNDED
            if payment.refunded_amount >= payment.amount
            else PaymentTransaction.Status.PARTIALLY_REFUNDED
        )
        payment.save(update_fields=["refunded_amount", "status", "updated_at"])
    elif refund.source_key.startswith("change:"):
        source_change_id = refund.source_key.split(":", 1)[1]
        extension = BookingChange.objects.select_for_update().get(
            pk=source_change_id, booking_id=change.booking_id,
        )
        extension.refunded_amount = min(extension.amount, money(extension.refunded_amount + amount))
        extension.refund_status = "INITIATED" if extension.refunded_amount else "NOT_REQUIRED"
        extension.save(update_fields=["refunded_amount", "refund_status", "updated_at"])
    change.refunded_amount = money(change.refunded_amount + amount)


def _mark_refund_initiated(refund, change, result):
    provider_status = str(result.get("status") or "pending").lower()
    if provider_status == "failed":
        refund.status = BookingRefund.Status.FAILED
        refund.provider_refund_id = str(result.get("id") or "")
        refund.provider_status = provider_status
        refund.error_message = "Razorpay marked this refund as failed."
        refund.save(update_fields=["status", "provider_refund_id", "provider_status", "error_message", "updated_at"])
        return False
    if str(result.get("payment_id") or refund.provider_payment_id) != refund.provider_payment_id:
        raise ValueError("Refund response did not match the captured payment.")
    if int(result.get("amount") or 0) != int(refund.amount * 100):
        raise ValueError("Refund response amount did not match the requested refund.")
    refund.status = BookingRefund.Status.INITIATED
    refund.provider_refund_id = str(result.get("id") or "")
    refund.provider_status = provider_status or "pending"
    refund.error_message = ""
    refund.save(update_fields=["status", "provider_refund_id", "provider_status", "error_message", "updated_at"])
    _apply_refund_to_source(refund, change)
    return True


def _finish_cancellation(change_id):
    with transaction.atomic():
        change = BookingChange.objects.select_for_update().select_related("booking").get(pk=change_id)
        refunds = list(change.refunds.select_for_update())
        if any(refund.status != BookingRefund.Status.INITIATED for refund in refunds):
            return False
        booking = Booking.objects.select_for_update().get(pk=change.booking_id)
        if booking.status != Booking.Status.CANCELLED:
            if change.refunded_amount and booking.financial_confirmed_at:
                base = max(Decimal("0.00"), money((booking.commissionable_base or 0) - change.refunded_amount))
                rate = Decimal(booking.commission_rate or 0)
                booking.commissionable_base = base
                booking.platform_commission = money(base * rate / Decimal("100"))
                booking.shopkeeper_net_earnings = money(base - booking.platform_commission)
                booking.save(update_fields=["commissionable_base", "platform_commission", "shopkeeper_net_earnings", "updated_at"])
                if change.refund_percent == 100:
                    booking.commission_reversed_at = timezone.now()
                    booking.save(update_fields=["commission_reversed_at", "updated_at"])
            booking.status = Booking.Status.CANCELLED
            if change.reason and change.requested_by.role != "USER":
                booking.shopkeeper_cancellation_reason = change.reason
            booking.save(update_fields=["status", "shopkeeper_cancellation_reason", "updated_at"])
        change.status = BookingChange.Status.COMPLETED
        change.refund_status = "INITIATED" if change.refunded_amount else "NOT_REQUIRED"
        change.save(update_fields=["status", "refund_status", "updated_at"])
        AuditLog.objects.create(
            actor=change.requested_by, action="booking_cancellation_completed",
            entity_type="booking", entity_id=booking.id,
            metadata={"change_id": change.id, "refund_percent": change.refund_percent, "refunded_amount": str(change.refunded_amount)},
        )
    return True


def process_cancellation(change_id):
    """Start every source refund once; preserve and retry the same receipt on ambiguity."""
    change = BookingChange.objects.select_related("booking").get(pk=change_id, kind=BookingChange.Kind.CANCEL)
    if change.status == BookingChange.Status.COMPLETED:
        return change, True
    for refund_id in change.refunds.values_list("id", flat=True):
        with transaction.atomic():
            refund = BookingRefund.objects.select_for_update().get(pk=refund_id)
            change = BookingChange.objects.select_for_update().get(pk=change_id)
            if refund.status == BookingRefund.Status.INITIATED:
                continue
            provider_refund = None
            if refund.status == BookingRefund.Status.FAILED:
                gateway = get_payment_gateway("RAZORPAY")
                provider_refund = _existing_provider_refund(gateway, refund)
                if provider_refund and str(provider_refund.get("status") or "").lower() == "failed":
                    # A provider-confirmed failure is safe to retry with a new
                    # receipt. If the result was merely lost, keep the old one.
                    refund.receipt = f"RH-RF-{uuid.uuid4().hex[:20]}"
                    refund.status = BookingRefund.Status.PENDING
                    refund.provider_status = "failed"
                    refund.error_message = "Retrying after the provider marked the previous refund failed."
                    refund.save(update_fields=["receipt", "status", "provider_status", "error_message", "updated_at"])
                    provider_refund = None
            else:
                gateway = get_payment_gateway("RAZORPAY")
            try:
                result = provider_refund or gateway.refund(refund.provider_payment_id, {
                    "amount": int(Decimal(refund.amount) * 100),
                    "receipt": refund.receipt,
                    "notes": {"booking_id": str(change.booking_id), "change_id": str(change.id), "reason": "RideHub cancellation"},
                })
                if not _mark_refund_initiated(refund, change, result):
                    continue
            except Exception:
                # If the gateway accepted the request but the response was
                # dropped, the deterministic receipt lets us recover it safely.
                refund.status = BookingRefund.Status.FAILED
                refund.error_message = "Refund could not be confirmed; a retry will reuse the same receipt."
                refund.save(update_fields=["status", "error_message", "updated_at"])
                continue
            change.save(update_fields=["refunded_amount", "updated_at"])
    completed = _finish_cancellation(change_id)
    change.refresh_from_db()
    return change, completed


def cancel_booking(*, booking_id, actor, refund_percent=None, reason="", customer_request=False):
    change = begin_cancellation(
        booking_id=booking_id, actor=actor, refund_percent=refund_percent,
        reason=reason, customer_request=customer_request,
    )
    if change.status == BookingChange.Status.COMPLETED:
        return change, True
    return process_cancellation(change.id)
