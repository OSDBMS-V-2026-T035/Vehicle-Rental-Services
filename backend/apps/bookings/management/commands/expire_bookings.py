from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.adminpanel.models import AuditLog
from apps.bookings.models import Booking


class Command(BaseCommand):
    help = "Cancel stale pending booking requests as a scheduled maintenance task."

    def add_arguments(self, parser):
        parser.add_argument("--older-than-hours", type=int, default=24)

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=max(1, options["older_than_hours"]))
        with transaction.atomic():
            stale = list(Booking.objects.filter(status=Booking.Status.PENDING, created_at__lt=cutoff).values_list("id", flat=True))
            updated = Booking.objects.filter(id__in=stale).update(status=Booking.Status.CANCELLED, updated_at=timezone.now())
            if updated:
                AuditLog.objects.create(action="booking_expiry_job", entity_type="booking_batch", metadata={"count": updated, "cutoff": cutoff.isoformat()})
        self.stdout.write(self.style.SUCCESS(f"Expired {updated} pending booking(s)."))
