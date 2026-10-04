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

    customer = models.ForeignKey(User, on_delete=models.PROTECT, related_name="bookings")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="bookings")
    pickup_date = models.DateField()
    return_date = models.DateField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["vehicle", "pickup_date", "return_date", "status"])]
        constraints = [models.CheckConstraint(condition=models.Q(return_date__gte=models.F("pickup_date")), name="booking_return_after_pickup")]

    def clean(self):
        if self.return_date < self.pickup_date:
            raise ValidationError("Return date must be on or after pickup date.")
