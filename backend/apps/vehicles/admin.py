from django.contrib import admin

from .models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        "display_name", "registration_number", "shopkeeper", "vehicle_type",
        "daily_rate", "listing_status", "is_available",
    )
    list_filter = ("vehicle_type", "listing_status", "is_available")
    search_fields = ("brand", "model_name", "registration_number", "shopkeeper__shop_name")
