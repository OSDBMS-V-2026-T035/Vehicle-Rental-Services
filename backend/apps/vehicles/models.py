from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from apps.accounts.models import ShopkeeperProfile


class Vehicle(models.Model):
    class VehicleType(models.TextChoices):
        CAR = "car", "Car"
        BIKE = "bike", "Bike"
        SCOOTER = "scooter", "Scooter"
        CYCLE = "cycle", "Cycle"
        COMMERCIAL = "commercial", "Commercial"

    class ListingStatus(models.TextChoices):
        PENDING = "PENDING", "Pending review"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    shopkeeper = models.ForeignKey(ShopkeeperProfile, on_delete=models.CASCADE, related_name="vehicles")
    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices)
    brand = models.CharField(max_length=80)
    model_name = models.CharField(max_length=120)
    registration_number = models.CharField(max_length=20, unique=True)
    manufacturing_year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1900), MaxValueValidator(2100)]
    )
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    seating_capacity = models.PositiveSmallIntegerField(
        default=2, validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    description = models.TextField(blank=True)
    image = models.FileField(upload_to="vehicle-images/%Y/%m/", blank=True, null=True)
    is_available = models.BooleanField(default=True)
    listing_status = models.CharField(
        max_length=20, choices=ListingStatus.choices, default=ListingStatus.PENDING
    )
    admin_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["vehicle_type", "listing_status", "is_available"]),
            models.Index(fields=["shopkeeper", "listing_status"]),
        ]

    def __str__(self):
        return f"{self.brand} {self.model_name} ({self.registration_number})"

    @property
    def display_name(self):
        return f"{self.brand} {self.model_name}"
