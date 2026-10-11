from django.contrib import admin

from .models import BookingVerification


@admin.register(BookingVerification)
class BookingVerificationAdmin(admin.ModelAdmin):
    list_display = ("booking", "document_type", "document_last4", "status", "method", "verified_at")
    list_filter = ("status", "method", "document_type")
    search_fields = ("booking__customer__email", "document_last4")
    readonly_fields = ("document_hash", "document_last4", "created_at")

