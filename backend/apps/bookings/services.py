from datetime import timedelta

from django.db import OperationalError, transaction
from django.utils import timezone
from decimal import Decimal

from .models import Booking
from apps.vehicles.models import Vehicle
from apps.verification.models import BookingVerification


PAYMENT_HOLD_MINUTES = 10
MYSQL_RETRYABLE_ERROR_CODES = {1205, 1213}


def _is_retryable_lock_error(error):
    """Return True only for MySQL's transient lock timeout/deadlock errors."""
    return bool(error.args and error.args[0] in MYSQL_RETRYABLE_ERROR_CODES)


def active_reservation_statuses():
    """Statuses that continue consuming inventory after checkout has settled."""
    return (Booking.Status.CONFIRMED, Booking.Status.HANDED_OVER)


def payment_hold_deadline():
    return timezone.now() + timedelta(minutes=PAYMENT_HOLD_MINUTES)


def expire_checkout_holds(now=None):
    """Release unpaid checkout holds which have passed their 10-minute deadline.

    The expiry timestamp is also used directly in availability queries, so an
    inventory unit becomes searchable at the deadline even if no worker is
    running at that exact second.  This routine records the final cancellation
    as soon as any normal booking/payment request next reaches the server.
    """
    from apps.payments.models import PaymentTransaction

    now = now or timezone.now()
    with transaction.atomic():
        expired = list(Booking.objects.select_for_update().filter(
            status=Booking.Status.PENDING,
            payment_expires_at__isnull=False,
            payment_expires_at__lte=now,
        ))
        if not expired:
            return 0
        booking_ids = [booking.id for booking in expired]
        Booking.objects.filter(id__in=booking_ids, status=Booking.Status.PENDING).update(
            status=Booking.Status.CANCELLED,
        )
        PaymentTransaction.objects.select_for_update().filter(
            booking_id__in=booking_ids,
            status=PaymentTransaction.Status.PENDING,
        ).update(status=PaymentTransaction.Status.CANCELLED)
    return len(expired)


def active_reservation_filter(now=None, relation_prefix=""):
    """Q expression for confirmed rides and still-live pending checkout holds.

    ``relation_prefix`` lets the same condition be used inside an aggregate on
    another model, e.g. ``bookings__`` when counting a vehicle's bookings.
    """
    from django.db.models import Q

    now = now or timezone.now()
    prefix = str(relation_prefix or "")
    status_field = f"{prefix}status"
    expiry_field = f"{prefix}payment_expires_at"
    # Null is retained for legacy pending records created before timed holds.
    return Q(**{f"{status_field}__in": active_reservation_statuses()}) | Q(
        **{status_field: Booking.Status.PENDING, f"{expiry_field}__isnull": True},
    ) | Q(
        **{status_field: Booking.Status.PENDING, f"{expiry_field}__gt": now},
    )


def create_locked_booking(*, customer, vehicle_id, pickup_date, return_date):
    """Create a booking while serialising competing requests for the same vehicle."""
    with transaction.atomic():
        expire_checkout_holds()
        try:
            vehicle = Vehicle.objects.select_for_update().get(
                pk=vehicle_id,
                listing_status=Vehicle.ListingStatus.APPROVED,
                is_available=True,
            )
        except Vehicle.DoesNotExist as exc:
            raise ValueError("This vehicle is unavailable.") from exc
        overlapping = Booking.objects.filter(
            vehicle=vehicle,
            pickup_date__lte=return_date,
            return_date__gte=pickup_date,
        ).filter(active_reservation_filter()).count()
        # The row lock is the inventory semaphore: competing requests for the
        # same listing are serialized before the fleet capacity is checked.
        if overlapping >= vehicle.quantity:
            raise ValueError("All units of this vehicle are reserved for the selected dates.")
        rental_days = max(1, (return_date - pickup_date).days)
        booking = Booking.objects.create(
            customer=customer,
            vehicle=vehicle,
            pickup_date=pickup_date,
            return_date=return_date,
            total_amount=Decimal(vehicle.daily_rate) * rental_days,
            status=Booking.Status.PENDING,
            payment_expires_at=payment_hold_deadline(),
        )
    return booking


def _create_checkout_booking(
    *, customer, vehicle_id, pickup_date, return_date, renter, aadhaar_hash, aadhaar_last4
):
    """Atomically reserve a vehicle and store a privacy-safe checkout snapshot."""
    with transaction.atomic():
        expire_checkout_holds()
        try:
            vehicle = Vehicle.objects.select_for_update().get(
                pk=vehicle_id,
                listing_status=Vehicle.ListingStatus.APPROVED,
                is_available=True,
            )
        except Vehicle.DoesNotExist as exc:
            raise ValueError("This vehicle is no longer available.") from exc

        overlapping = Booking.objects.filter(
            vehicle=vehicle,
            pickup_date__lte=return_date,
            return_date__gte=pickup_date,
        ).filter(active_reservation_filter()).count()
        if overlapping >= vehicle.quantity:
            raise ValueError("All units of this vehicle were just reserved for the selected dates.")

        rental_days = max(1, (return_date - pickup_date).days)
        booking = Booking.objects.create(
            customer=customer,
            vehicle=vehicle,
            pickup_date=pickup_date,
            return_date=return_date,
            total_amount=Decimal(vehicle.daily_rate) * rental_days,
            renter_full_name=renter["full_name"],
            renter_age=renter["age"],
            renter_gender=renter["gender"],
            renter_phone=renter["phone"],
            renter_email=renter["email"],
            email_verified_at=timezone.now(),
            payment_expires_at=payment_hold_deadline(),
            status=Booking.Status.PENDING,
        )
        BookingVerification.objects.create(
            booking=booking,
            document_hash=aadhaar_hash,
            document_last4=aadhaar_last4,
            status=BookingVerification.Status.VERIFIED_FORMAT,
            method=BookingVerification.Method.VERHOEFF,
            verified_at=timezone.now(),
        )
    return booking


def create_checkout_booking(**kwargs):
    """Reserve a checkout unit, retrying a short-lived MySQL lock conflict once.

    Availability search and checkout can arrive together.  MySQL may pick one
    transaction as a deadlock victim even though no database service is down.
    Retrying that known transient error keeps the customer flow reliable while
    preserving the row-lock inventory guarantee in ``_create_checkout_booking``.
    """
    for attempt in range(2):
        try:
            return _create_checkout_booking(**kwargs)
        except OperationalError as exc:
            if attempt or not _is_retryable_lock_error(exc):
                raise
