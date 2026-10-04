from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "customer", "pickup_date", "return_date", "status", "total_amount")
    list_filter = ("status", "pickup_date", "return_date")
    search_fields = ("vehicle__registration_number", "customer__email")
