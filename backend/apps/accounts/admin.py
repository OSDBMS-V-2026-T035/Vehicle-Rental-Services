from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import OTPChallenge, ShopkeeperProfile, User


@admin.register(User)
class AccountUserAdmin(UserAdmin):
    ordering = ("-created_at",)
    list_display = ("email", "phone_number", "role", "is_email_verified", "is_phone_verified", "is_active")
    list_filter = ("role", "is_email_verified", "is_phone_verified", "is_active")
    search_fields = ("email", "phone_number", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "password")} ),
        ("Profile", {"fields": ("first_name", "last_name", "phone_number", "role")} ),
        ("Verification", {"fields": ("is_email_verified", "is_phone_verified")} ),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")} ),
        ("Important dates", {"fields": ("last_login", "date_joined", "created_at", "updated_at")} ),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "phone_number", "password1", "password2", "role")} ),
    )
    readonly_fields = ("created_at", "updated_at", "date_joined", "last_login")


@admin.register(ShopkeeperProfile)
class ShopkeeperProfileAdmin(admin.ModelAdmin):
    list_display = ("shop_name", "user", "verification_status", "created_at")
    list_filter = ("verification_status",)
    search_fields = ("shop_name", "user__email", "user__phone_number")


@admin.register(OTPChallenge)
class OTPChallengeAdmin(admin.ModelAdmin):
    list_display = ("contact", "channel", "purpose", "expires_at", "verified_at", "created_at")
    list_filter = ("channel", "purpose", "verified_at")
    search_fields = ("contact",)
    readonly_fields = ("code_hash", "created_at", "request_ip")
