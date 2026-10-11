from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from .models import Booking
from apps.vehicles.models import Vehicle
from apps.verification.models import BookingVerification


def create_locked_booking(*, customer, vehicle_id, pickup_date, return_date):
    """Create a booking while serialising competing requests for the same vehicle."""
    with transaction.atomic():
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
            status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED],
            pickup_date__lte=return_date,
            return_date__gte=pickup_date,
        ).count()
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
        )
    return booking


def create_checkout_booking(
    *, customer, vehicle_id, pickup_date, return_date, renter, aadhaar_hash, aadhaar_last4
):
    """Atomically reserve a vehicle and store a privacy-safe checkout snapshot."""
    with transaction.atomic():
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
            status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED],
            pickup_date__lte=return_date,
            return_date__gte=pickup_date,
        ).count()
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
