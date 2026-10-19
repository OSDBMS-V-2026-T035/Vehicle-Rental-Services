"""Fail fast when RideHub is started against an incompatible database."""

import os

from django.contrib.auth import authenticate
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Verify database schema, migration state, and optional admin login before serving traffic."

    def add_arguments(self, parser):
        parser.add_argument(
            "--require-admin",
            action="store_true",
            help="Require the RIDEHUB_ADMIN_* credentials to authenticate successfully.",
        )

    def handle(self, *args, **options):
        try:
            connection.ensure_connection()
        except Exception as exc:
            raise CommandError("RideHub cannot connect to its database.") from exc

        if connection.vendor == "mysql" and connection.mysql_version < (8, 0, 11):
            raise CommandError("RideHub requires MySQL 8.0.11 or later (MySQL 8.4 recommended).")

        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if pending:
            names = ", ".join(f"{migration.app_label}.{migration.name}" for migration, _backwards in pending)
            raise CommandError(f"Unapplied migrations: {names}")

        with connection.cursor() as cursor:
            booking_columns = {
                description.name
                for description in connection.introspection.get_table_description(cursor, "bookings_booking")
            }
        if "lifecycle_note" not in booking_columns:
            raise CommandError("Booking schema is missing lifecycle_note. Run migrations before starting RideHub.")

        if options["require_admin"]:
            email = os.getenv("RIDEHUB_ADMIN_EMAIL", "").strip().lower()
            password = os.getenv("RIDEHUB_ADMIN_PASSWORD", "")
            admin = authenticate(username=email, password=password) if email and password else None
            if not admin or admin.role != User.Role.ADMIN or not admin.is_active or not admin.is_email_verified:
                raise CommandError("Configured administrator credentials failed the startup authentication check.")

        self.stdout.write(self.style.SUCCESS("RideHub runtime verification passed."))
