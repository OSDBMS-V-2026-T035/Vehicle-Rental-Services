"""Customer initiated booking date changes."""

import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.adminpanel.models import AuditLog
from apps.payments.models import PaymentTransaction
from .finance import add_paid_extension
from .models import Booking, BookingChange
from .services import active_reservation_count, payment_hold_deadline


MAX_RENTAL_DAYS = 7
OPEN_CHANGE_STATUSES = (BookingChange.Status.PENDING_PAYMENT, BookingChange.Status.PROCESSING)


def _payload(request):
    try:
        return json.loads(request.body or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}


def _load_customer_booking(customer, booking_id):
    try:
        booking = Booking.objects.select_for_update().select_related("vehicle", "payment").get(
            pk=booking_id, customer=customer,
        )
    except Booking.DoesNotExist as exc:
        raise LookupError("Booking not found.") from exc
    if BookingChange.objects.filter(booking=booking, status__in=OPEN_CHANGE_STATUSES).exists():
        raise ValueError("Finish or cancel the current booking change before starting another.")
    return booking


def prepare_reschedule(*, customer, booking_id, new_pickup):
    """Move an unpaid-to-shop-confirmed booking while preserving its duration."""
    with transaction.atomic():
        booking = _load_customer_booking(customer, booking_id)
        if booking.status != Booking.Status.CONFIRMED:
            raise ValueError("Reschedule is available before pickup on confirmed bookings only.")
        if not hasattr(booking, "payment") or booking.payment.status not in {
            PaymentTransaction.Status.PAID, PaymentTransaction.Status.PARTIALLY_REFUNDED,
        }:
            raise ValueError("A verified paid booking is required to reschedule.")
        today = timezone.localdate()
        if booking.pickup_date < today or new_pickup < today:
            raise ValueError("Rescheduling must be completed before pickup, and the new pickup cannot be in the past.")
        duration = (booking.return_date - booking.pickup_date).days
        if duration < 1 or duration > MAX_RENTAL_DAYS:
            raise ValueError("This booking duration cannot be rescheduled online.")
        new_return = new_pickup + timedelta(days=duration)
        vehicle = booking.vehicle.__class__.objects.select_for_update().get(pk=booking.vehicle_id)
        occupied = active_reservation_count(
            vehicle_id=vehicle.id, pickup_date=new_pickup, return_date=new_return,
            exclude_booking_id=booking.id,
        )
        if occupied >= vehicle.quantity:
            raise ValueError("Those dates are already at capacity. Choose another pickup date.")
        old_pickup, old_return = booking.pickup_date, booking.return_date
        change = BookingChange.objects.create(
            booking=booking, requested_by=customer,
            kind=BookingChange.Kind.RESCHEDULE, status=BookingChange.Status.COMPLETED,
            from_pickup=old_pickup, from_return=old_return,
            to_pickup=new_pickup, to_return=new_return,
        )
        booking.pickup_date, booking.return_date = new_pickup, new_return
        booking.save(update_fields=["pickup_date", "return_date", "updated_at"])
        AuditLog.objects.create(
            actor=customer, action="booking_rescheduled", entity_type="booking", entity_id=booking.id,
            metadata={"change_id": change.id, "pickup_date": new_pickup.isoformat(), "return_date": new_return.isoformat()},
        )
    return booking, change


def prepare_extension(*, customer, booking_id, new_return):
    """Reserve the added dates and create a short-lived payment change record."""
    with transaction.atomic():
        booking = _load_customer_booking(customer, booking_id)
        if booking.status not in {Booking.Status.CONFIRMED, Booking.Status.HANDED_OVER}:
            raise ValueError("Only an active, paid booking can be extended.")
        if not hasattr(booking, "payment") or booking.payment.status not in {
            PaymentTransaction.Status.PAID, PaymentTransaction.Status.PARTIALLY_REFUNDED,
        }:
            raise ValueError("A verified paid booking is required to extend.")
        if booking.return_date < timezone.localdate():
            raise ValueError("This booking has already passed its return date.")
        if new_return <= booking.return_date:
            raise ValueError("Choose a return date after the current return date.")
        current_days = max(1, (booking.return_date - booking.pickup_date).days)
        added_days = (new_return - booking.return_date).days
        if current_days + added_days > MAX_RENTAL_DAYS:
            raise ValueError(f"A booking can cover at most {MAX_RENTAL_DAYS} rental days online.")
        vehicle = booking.vehicle.__class__.objects.select_for_update().get(pk=booking.vehicle_id)
        occupied = active_reservation_count(
            vehicle_id=vehicle.id, pickup_date=booking.return_date, return_date=new_return,
            exclude_booking_id=booking.id,
        )
        if occupied >= vehicle.quantity:
            raise ValueError("The vehicle is not available for the full extension period.")
        if booking.daily_rate_snapshot is not None:
            daily_rate = Decimal(booking.daily_rate_snapshot)
        else:
            original_base = booking.commissionable_base or booking.total_amount
            daily_rate = Decimal(original_base) / Decimal(current_days)
        added_amount = (daily_rate * added_days).quantize(Decimal("0.01"))
        if added_amount <= 0:
            raise ValueError("The additional rental amount is invalid.")
        change = BookingChange.objects.create(
            booking=booking, requested_by=customer,
            kind=BookingChange.Kind.EXTEND, status=BookingChange.Status.PENDING_PAYMENT,
            from_pickup=booking.pickup_date, from_return=booking.return_date,
            to_pickup=booking.return_date, to_return=new_return,
            amount=added_amount, provider="RAZORPAY",
            expires_at=payment_hold_deadline(),
        )
        AuditLog.objects.create(
            actor=customer, action="booking_extension_payment_started", entity_type="booking", entity_id=booking.id,
            metadata={"change_id": change.id, "to_return": new_return.isoformat(), "amount": str(added_amount)},
        )
    return booking, change


def apply_paid_extension(*, change_id, provider_payment_id):
    """Finalize a verified add-on payment and the new inventory return date."""
    with transaction.atomic():
        change = BookingChange.objects.select_for_update().select_related("booking").get(
            pk=change_id, kind=BookingChange.Kind.EXTEND,
        )
        if change.status == BookingChange.Status.COMPLETED:
            if change.provider_payment_id == provider_payment_id:
                return change.booking
            raise ValueError("This extension payment was already completed.")
        if change.status != BookingChange.Status.PENDING_PAYMENT:
            raise ValueError("This extension checkout is no longer active.")
        if change.expires_at and change.expires_at <= timezone.now():
            change.status = BookingChange.Status.EXPIRED
            change.save(update_fields=["status", "updated_at"])
            raise ValueError("The extension payment window expired. Contact support if money was deducted.")
        booking = Booking.objects.select_for_update().select_related("vehicle").get(pk=change.booking_id)
        if booking.status not in {Booking.Status.CONFIRMED, Booking.Status.HANDED_OVER}:
            raise ValueError("This booking can no longer be extended.")
        vehicle = booking.vehicle.__class__.objects.select_for_update().get(pk=booking.vehicle_id)
        occupied = active_reservation_count(
            vehicle_id=vehicle.id, pickup_date=change.from_return, return_date=change.to_return,
            exclude_booking_id=booking.id,
        )
        if occupied >= vehicle.quantity:
            raise ValueError("The requested extension dates are no longer available.")
        booking.return_date = change.to_return
        add_paid_extension(booking, change.amount)
        change.provider_payment_id = provider_payment_id
        change.status = BookingChange.Status.COMPLETED
        change.expires_at = None
        change.save(update_fields=["provider_payment_id", "status", "expires_at", "updated_at"])
        AuditLog.objects.create(
            actor=change.requested_by, action="booking_extension_paid", entity_type="booking", entity_id=booking.id,
            metadata={"change_id": change.id, "to_return": change.to_return.isoformat(), "amount": str(change.amount)},
        )
    return booking


@login_required
@require_POST
def reschedule_customer_booking(request, booking_id):
    if request.user.role != User.Role.USER:
        return JsonResponse({"ok": False, "message": "Customer access only."}, status=403)
    new_pickup = parse_date(str(_payload(request).get("pickup_date") or ""))
    if not new_pickup:
        return JsonResponse({"ok": False, "message": "Choose a valid new pickup date."}, status=400)
    try:
        booking, change = prepare_reschedule(customer=request.user, booking_id=booking_id, new_pickup=new_pickup)
    except LookupError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=404)
    except ValueError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=409)
    return JsonResponse({
        "ok": True, "message": "Booking dates updated. No extra payment was needed.",
        "change_id": change.id, "pickup_date": booking.pickup_date.isoformat(),
        "return_date": booking.return_date.isoformat(),
    })


def parse_extension_date(request):
    return parse_date(str(_payload(request).get("return_date") or ""))
