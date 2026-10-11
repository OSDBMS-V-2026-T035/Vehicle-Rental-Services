from django.conf import settings
from django.db import models


class PaymentTransaction(models.Model):
    """A payment lifecycle record; a payment gateway is intentionally separate."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending payment"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"
        CANCELLED = "CANCELLED", "Cancelled"

    booking = models.OneToOneField("bookings.Booking", on_delete=models.PROTECT, related_name="payment")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payment_transactions")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    provider = models.CharField(max_length=40, blank=True)
    provider_reference = models.CharField(max_length=120, blank=True)
    provider_payment_id = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["customer", "status", "created_at"])]

    def __str__(self):
        return f"Payment for booking #{self.booking_id} ({self.status})"
