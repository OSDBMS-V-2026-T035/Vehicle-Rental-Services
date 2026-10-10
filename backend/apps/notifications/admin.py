from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "email_sent", "created_at", "read_at")
    list_filter = ("email_sent", "created_at")
    search_fields = ("user__email", "title", "message")
