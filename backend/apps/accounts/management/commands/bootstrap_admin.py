import os

from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError, transaction

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create or update the protected RideHub administrator account from environment values."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=None, help="Admin login email; defaults to RIDEHUB_ADMIN_EMAIL.")
        parser.add_argument("--password", default=None, help="Admin password; defaults to RIDEHUB_ADMIN_PASSWORD.")
        parser.add_argument("--phone", default=None, help="Admin contact number; defaults to RIDEHUB_ADMIN_PHONE.")

    def handle(self, *args, **options):
        email = (options["email"] or os.getenv("RIDEHUB_ADMIN_EMAIL", "ridehub@admin.ride")).strip().lower()
        password = options["password"] or os.getenv("RIDEHUB_ADMIN_PASSWORD", "")
        phone = (options["phone"] or os.getenv("RIDEHUB_ADMIN_PHONE", "9999999999")).strip()
        if not password:
            raise CommandError("Set RIDEHUB_ADMIN_PASSWORD in the local env file or pass --password.")
        if not email or not phone:
            raise CommandError("Admin email and phone are required.")

        try:
            with transaction.atomic():
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "phone_number": phone,
                        "first_name": "RideHub",
                        "last_name": "Admin",
                    },
                )
                user.phone_number = phone
                user.first_name = "RideHub"
                user.last_name = "Admin"
                user.role = User.Role.ADMIN
                user.is_active = True
                user.is_staff = True
                user.is_superuser = True
                user.is_email_verified = True
                user.set_password(password)
                user.save(update_fields=[
                    "phone_number", "first_name", "last_name", "role", "is_active",
                    "is_staff", "is_superuser", "is_email_verified", "password", "updated_at",
                ])
        except OperationalError as exc:
            raise CommandError("MySQL is unavailable. Start MySQL and run `python backend/manage.py bootstrap_admin` again.") from exc

        state = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"RideHub admin account {state}: {email}"))
