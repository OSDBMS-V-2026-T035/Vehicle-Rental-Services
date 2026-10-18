"""Secure one-time pickup and return handover operations."""

import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.adminpanel.models import AuditLog
from apps.bookings.models import Booking, BookingInspection
from apps.payments.models import PaymentTransaction


HANDOVER_CODE_TTL_MINUTES = 10
HANDOVER_CODE_RESEND_SECONDS = 30
HANDOVER_CODE_MAX_ATTEMPTS = 5
CHECKLIST_FIELDS = ("exterior", "lights", "tires", "brakes", "mirrors", "documents", "keys")


def validate_inspection_payload(payload):
    """Return normalized inspection values or raise a user-safe ValueError."""
    try:
        odometer = int(payload.get("odometer_km"))
        fuel = int(payload.get("fuel_percent"))
    except (TypeError, ValueError):
        raise ValueError("Enter a valid odometer reading and fuel percentage.")
    if isinstance(payload.get("odometer_km"), bool) or not 0 <= odometer <= 2_000_000:
        raise ValueError("Odometer must be a whole number between 0 and 2,000,000 km.")
    if isinstance(payload.get("fuel_percent"), bool) or not 0 <= fuel <= 100:
        raise ValueError("Fuel/battery level must be a whole percentage from 0 to 100.")
    checklist = payload.get("condition_checklist")
    if not isinstance(checklist, dict) or set(checklist) != set(CHECKLIST_FIELDS):
        raise ValueError("Complete every vehicle condition checklist item.")
    if any(not isinstance(checklist[field], bool) for field in CHECKLIST_FIELDS):
        raise ValueError("Every checklist item must be marked as passed or needs attention.")
    notes = " ".join(str(payload.get("notes") or "").split())
    if len(notes) > 1000:
        raise ValueError("Inspection notes must be 1,000 characters or fewer.")
    return {
        "odometer_km": odometer,
        "fuel_percent": fuel,
        "condition_checklist": {field: checklist[field] for field in CHECKLIST_FIELDS},
        "notes": notes,
    }


def issue_handover_code(*, customer, booking_id, stage, now=None):
    """Issue a short-lived code to the booking owner; only a hash is persisted."""
    now = now or timezone.now()
    if stage not in BookingInspection.Stage.values:
        raise ValueError("Choose a valid pickup or return stage.")
    expected_status = (
        Booking.Status.CONFIRMED if stage == BookingInspection.Stage.PICKUP
        else Booking.Status.HANDED_OVER
    )
    with transaction.atomic():
        try:
            booking = Booking.objects.select_for_update().get(pk=booking_id, customer=customer)
        except Booking.DoesNotExist as exc:
            raise LookupError("Booking not found.") from exc
        if booking.status != expected_status:
            raise ValueError("This booking is not at the selected handover stage.")
        if not PaymentTransaction.objects.filter(
            booking=booking, customer=customer, status=PaymentTransaction.Status.PAID
        ).exists():
            raise ValueError("A verified payment is required before handover.")
        inspection = BookingInspection.objects.select_for_update().filter(booking=booking, stage=stage).first()
        if inspection and inspection.status == BookingInspection.Status.CONFIRMED:
            raise ValueError("This inspection stage has already been completed.")
        if inspection and inspection.expires_at > now and inspection.updated_at > now - timedelta(seconds=HANDOVER_CODE_RESEND_SECONDS):
            raise TimeoutError("Wait 30 seconds before requesting another handover code.")
        code = f"{secrets.randbelow(1_000_000):06d}"
        defaults = {
            "status": BookingInspection.Status.PENDING,
            "code_hash": make_password(code),
            "expires_at": now + timedelta(minutes=HANDOVER_CODE_TTL_MINUTES),
            "attempts": 0,
            "odometer_km": None,
            "fuel_percent": None,
            "condition_checklist": {},
            "notes": "",
            "recorded_by": None,
            "confirmed_at": None,
        }
        BookingInspection.objects.update_or_create(booking=booking, stage=stage, defaults=defaults)
    return {"code": code, "expires_at": now + timedelta(minutes=HANDOVER_CODE_TTL_MINUTES)}


def record_handover_inspection(*, profile, booking_id, stage, code, payload, now=None):
    """Validate a customer-issued code and atomically record the shop inspection."""
    now = now or timezone.now()
    values = validate_inspection_payload(payload)
    if stage not in BookingInspection.Stage.values:
        raise ValueError("Choose a valid pickup or return stage.")
    expected_status = (
        Booking.Status.CONFIRMED if stage == BookingInspection.Stage.PICKUP
        else Booking.Status.HANDED_OVER
    )
    next_status = (
        Booking.Status.HANDED_OVER if stage == BookingInspection.Stage.PICKUP
        else Booking.Status.COMPLETED
    )
    failure = None
    with transaction.atomic():
        try:
            booking = Booking.objects.select_for_update().get(pk=booking_id, vehicle__shopkeeper=profile)
        except Booking.DoesNotExist as exc:
            raise LookupError("Reservation not found.") from exc
        if booking.status != expected_status:
            raise ValueError("This booking is not at the selected handover stage.")
        inspection = BookingInspection.objects.select_for_update().filter(booking=booking, stage=stage).first()
        if not inspection or inspection.status != BookingInspection.Status.PENDING:
            raise ValueError("Ask the customer to generate a fresh handover code first.")
        if inspection.expires_at <= now:
            inspection.status = BookingInspection.Status.EXPIRED
            inspection.save(update_fields=["status", "updated_at"])
            failure = "Handover code expired. Ask the customer to generate a new one."
        elif inspection.attempts >= HANDOVER_CODE_MAX_ATTEMPTS:
            failure = "Too many incorrect attempts. Ask the customer to generate a new code."
        elif not check_password(str(code or "").strip(), inspection.code_hash):
            inspection.attempts += 1
            if inspection.attempts >= HANDOVER_CODE_MAX_ATTEMPTS:
                inspection.status = BookingInspection.Status.EXPIRED
            inspection.save(update_fields=["attempts", "status", "updated_at"])
            failure = "Handover code is incorrect. Check with the customer and try again."
        else:
            inspection.status = BookingInspection.Status.CONFIRMED
            inspection.odometer_km = values["odometer_km"]
            inspection.fuel_percent = values["fuel_percent"]
            inspection.condition_checklist = values["condition_checklist"]
            inspection.notes = values["notes"]
            inspection.recorded_by = profile.user
            inspection.confirmed_at = now
            inspection.save(update_fields=[
                "status", "odometer_km", "fuel_percent", "condition_checklist", "notes",
                "recorded_by", "confirmed_at", "updated_at",
            ])
            booking.status = next_status
            if stage == BookingInspection.Stage.PICKUP:
                booking.handover_at = now
                fields = ["status", "handover_at", "updated_at"]
            else:
                booking.received_back_at = now
                fields = ["status", "received_back_at", "updated_at"]
            booking.save(update_fields=fields)
            AuditLog.objects.create(
                actor=profile.user,
                action=f"booking_{stage.lower()}_inspection_recorded",
                entity_type="booking",
                entity_id=booking.id,
                metadata={
                    "odometer_km": values["odometer_km"],
                    "fuel_percent": values["fuel_percent"],
                    "condition_checklist": values["condition_checklist"],
                },
            )
    if failure:
        raise ValueError(failure)
    return booking
