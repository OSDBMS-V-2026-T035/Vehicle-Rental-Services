from django.core.exceptions import ValidationError
from django.db import models

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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["vehicle", "pickup_date", "return_date", "status"])]
        constraints = [models.CheckConstraint(condition=models.Q(return_date__gte=models.F("pickup_date")), name="booking_return_after_pickup")]

    def clean(self):
        if self.return_date < self.pickup_date:
            raise ValidationError("Return date must be on or after pickup date.")
