from django.core.exceptions import ValidationError
from django.db import models
from django.core.validators import MaxValueValidator

from apps.accounts.models import User
from apps.vehicles.models import Vehicle


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"
        HANDED_OVER = "HANDED_OVER", "Vehicle handed over"

    customer = models.ForeignKey(User, on_delete=models.PROTECT, related_name="bookings")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="bookings")
    pickup_date = models.DateField()
    return_date = models.DateField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    # Financial terms are frozen when a payment is captured.  ``total_amount``
    # remains the authoritative customer payable amount for legacy callers.
    commissionable_base = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    platform_commission = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    shopkeeper_net_earnings = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    financial_calculation_version = models.PositiveSmallIntegerField(default=1)
    financial_confirmed_at = models.DateTimeField(null=True, blank=True)
    commission_reversed_at = models.DateTimeField(null=True, blank=True)
    renter_full_name = models.CharField(max_length=150, blank=True)
    renter_age = models.PositiveSmallIntegerField(null=True, blank=True)
    renter_gender = models.CharField(max_length=24, blank=True)
    renter_phone = models.CharField(max_length=10, blank=True)
    renter_email = models.EmailField(blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    # A pending checkout owns one inventory unit only for this short window.
    # Confirmed bookings are never subject to this deadline.
    payment_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    handover_at = models.DateTimeField(null=True, blank=True)
    received_back_at = models.DateTimeField(null=True, blank=True)
    shopkeeper_cancellation_reason = models.TextField(blank=True)
    # Kept for compatibility with earlier RideHub databases that recorded a
    # lifecycle comment for every booking.  A default is essential because
    # those databases still require this column during inserts.
    lifecycle_note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["vehicle", "pickup_date", "return_date", "status"])]
        constraints = [models.CheckConstraint(condition=models.Q(return_date__gte=models.F("pickup_date")), name="booking_return_after_pickup")]

    def clean(self):
        if self.return_date < self.pickup_date:
            raise ValidationError("Return date must be on or after pickup date.")


class BookingInspection(models.Model):
    """Customer-authorized, one-time pickup/return inspection for a booking."""

    class Stage(models.TextChoices):
        PICKUP = "PICKUP", "Pickup"
        RETURN = "RETURN", "Return"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Awaiting shop inspection"
        CONFIRMED = "CONFIRMED", "Inspection recorded"
        EXPIRED = "EXPIRED", "Code expired"

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="inspections")
    stage = models.CharField(max_length=10, choices=Stage.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    odometer_km = models.PositiveIntegerField(null=True, blank=True)
    fuel_percent = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(100)])
    condition_checklist = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="recorded_vehicle_inspections"
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["stage"]
        constraints = [
            models.UniqueConstraint(fields=["booking", "stage"], name="unique_booking_inspection_stage"),
        ]
        indexes = [models.Index(fields=["status", "expires_at"]) ]
