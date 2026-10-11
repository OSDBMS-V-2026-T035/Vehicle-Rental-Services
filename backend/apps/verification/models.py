from django.db import models


class BookingVerification(models.Model):
    """Privacy-conscious identity snapshot captured for a booking."""

    class Status(models.TextChoices):
        VERIFIED_FORMAT = "VERIFIED_FORMAT", "Format verified"
        PENDING_REVIEW = "PENDING_REVIEW", "Pending review"

    class Method(models.TextChoices):
        VERHOEFF = "VERHOEFF", "Aadhaar checksum"
        MANUAL = "MANUAL", "Manual review"

    booking = models.OneToOneField(
        "bookings.Booking", on_delete=models.CASCADE, related_name="identity_verification"
    )
    document_type = models.CharField(max_length=32, default="AADHAAR")
    document_hash = models.CharField(max_length=128)
    document_last4 = models.CharField(max_length=4)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING_REVIEW)
    method = models.CharField(max_length=16, choices=Method.choices, default=Method.VERHOEFF)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"Booking #{self.booking_id} identity verification"

