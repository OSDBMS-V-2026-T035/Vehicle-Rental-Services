from django.db import transaction
from decimal import Decimal

from .models import Booking
from apps.vehicles.models import Vehicle


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
        conflict = Booking.objects.filter(
            vehicle=vehicle,
            status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED],
            pickup_date__lte=return_date,
            return_date__gte=pickup_date,
        ).exists()
        if conflict:
            raise ValueError("This vehicle is already reserved for the selected dates.")
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
