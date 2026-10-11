import json
from datetime import timedelta
import re

from django.contrib.auth.decorators import login_required
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import User
from apps.notifications.services import notify_user
from apps.payments.models import PaymentTransaction
from apps.adminpanel.models import AuditLog
from apps.vehicles.models import Vehicle
from .models import Booking
from .services import create_checkout_booking, create_locked_booking
from apps.accounts.models import phone_validator
from apps.verification.services import validate_aadhaar


def _payload(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}


@login_required
@require_POST
def create_booking(request):
    if request.user.role != User.Role.USER:
        return JsonResponse({"ok": False, "message": "Only customer accounts can create bookings."}, status=403)
    payload = _payload(request)
    pickup_date = parse_date(str(payload.get("pickup_date", "")))
    return_date = parse_date(str(payload.get("return_date", "")))
    if not pickup_date or not return_date:
        return JsonResponse({"ok": False, "message": "Choose valid pickup and return dates."}, status=400)
    if pickup_date < timezone.localdate():
        return JsonResponse({"ok": False, "message": "Pickup date cannot be in the past."}, status=400)
    if return_date < pickup_date or return_date > pickup_date + timedelta(days=7):
        return JsonResponse({"ok": False, "message": "Return date must be within 7 days of pickup."}, status=400)
    try:
        booking = create_locked_booking(
            customer=request.user,
            vehicle_id=int(payload.get("vehicle_id")),
            pickup_date=pickup_date,
            return_date=return_date,
        )
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "message": "This vehicle is unavailable for the selected dates."}, status=409)
    payment, _ = PaymentTransaction.objects.get_or_create(
        booking=booking,
        defaults={"customer": request.user, "amount": booking.total_amount},
    )
    notify_user(request.user, "Booking request received", f"Your booking request for {booking.vehicle.display_name} is ready for secure payment.")
    notify_user(booking.vehicle.shopkeeper.user, "New booking request", f"A customer requested {booking.vehicle.display_name} from {pickup_date.isoformat()} to {return_date.isoformat()}. Review it after payment is verified.")
    return JsonResponse({
        "ok": True,
        "message": "Booking request created safely.",
        "booking_id": booking.id,
        "payment_id": payment.id,
        "total_amount": str(booking.total_amount),
    })


@login_required
@require_POST
def create_checkout_booking_view(request):
    """Validate the renter identity and reserve a vehicle before payment work begins."""
    if request.user.role != User.Role.USER:
        return JsonResponse({"ok": False, "message": "Only customer accounts can create bookings."}, status=403)
    if not request.user.is_email_verified:
        return JsonResponse({"ok": False, "message": "Verify your RideHub email before continuing."}, status=403)
    payload = _payload(request)
    pickup_date = parse_date(str(payload.get("pickup_date", "")))
    return_date = parse_date(str(payload.get("return_date", "")))
    if not pickup_date or not return_date:
        return JsonResponse({"ok": False, "message": "Choose valid pickup and return dates."}, status=400)
    if pickup_date < timezone.localdate():
        return JsonResponse({"ok": False, "message": "Pickup date cannot be in the past."}, status=400)
    if return_date < pickup_date or return_date > pickup_date + timedelta(days=7):
        return JsonResponse({"ok": False, "message": "Return date must be within 7 days of pickup."}, status=400)

    full_name = " ".join(str(payload.get("full_name", "")).strip().split())
    email = str(payload.get("email", "")).strip().lower()
    phone = re.sub(r"\D", "", str(payload.get("phone", "")))
    gender = str(payload.get("gender", "")).strip().lower()
    try:
        age = int(payload.get("age", 0))
    except (TypeError, ValueError):
        age = 0
    if len(full_name) < 2 or len(full_name) > 150:
        return JsonResponse({"ok": False, "message": "Enter your full legal name."}, status=400)
    if age < 18 or age > 90:
        return JsonResponse({"ok": False, "message": "The renter must be between 18 and 90 years old."}, status=400)
    if gender not in {"male", "female", "non_binary", "prefer_not_to_say"}:
        return JsonResponse({"ok": False, "message": "Choose a valid gender option."}, status=400)
    try:
        validate_email(email)
        phone_validator(phone)
    except ValidationError as exc:
        return JsonResponse({"ok": False, "message": exc.messages[0]}, status=400)
    if email != request.user.email.lower():
        return JsonResponse({"ok": False, "message": "Use the verified email on your RideHub account."}, status=400)
    valid_aadhaar, identity = validate_aadhaar(payload.get("aadhaar"))
    if not valid_aadhaar:
        return JsonResponse({"ok": False, "message": "Enter a valid 12-digit Aadhaar number with a valid checksum."}, status=400)
    try:
        booking = create_checkout_booking(
            customer=request.user,
            vehicle_id=int(payload.get("vehicle_id")),
            pickup_date=pickup_date,
            return_date=return_date,
            renter={"full_name": full_name, "age": age, "gender": gender, "phone": phone, "email": email},
            aadhaar_hash=identity[0],
            aadhaar_last4=identity[1],
        )
    except (TypeError, ValueError, ValidationError) as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=409)
    payment, _ = PaymentTransaction.objects.get_or_create(
        booking=booking,
        defaults={"customer": request.user, "amount": booking.total_amount},
    )
    notify_user(request.user, "Booking request received", f"Your booking request for {booking.vehicle.display_name} is ready for secure payment.")
    notify_user(booking.vehicle.shopkeeper.user, "New booking request", f"A customer requested {booking.vehicle.display_name} from {pickup_date.isoformat()} to {return_date.isoformat()}. Review it after payment is verified.")
    return JsonResponse({
        "ok": True,
        "message": "Your booking request is saved. Complete the secure payment to send it for shop review.",
        "booking_id": booking.id,
        "payment_id": payment.id,
        "total_amount": str(booking.total_amount),
        "status": booking.status,
    })


@login_required
@require_GET
def booking_history(request):
    bookings = Booking.objects.filter(customer=request.user).select_related("vehicle", "vehicle__shopkeeper")
    return JsonResponse({
        "ok": True,
        "bookings": [
            {
                "id": booking.id,
                "vehicle": booking.vehicle.display_name,
                "shop": booking.vehicle.shopkeeper.shop_name,
                "pickup_date": booking.pickup_date.isoformat(),
                "return_date": booking.return_date.isoformat(),
                "status": booking.status,
                "total_amount": str(booking.total_amount),
                "renter_name": booking.renter_full_name,
                "identity_verified": hasattr(booking, "identity_verification"),
            }
            for booking in bookings
        ],
    })


@login_required
@require_POST
def shopkeeper_booking_action(request, booking_id):
    """Confirm or cancel a booking belonging to the authenticated shopkeeper."""
    if request.user.role != User.Role.SHOPKEEPER:
        return JsonResponse({"ok": False, "message": "Shopkeeper access only."}, status=403)
    profile = getattr(request.user, "shopkeeper_profile", None)
    if not profile or profile.verification_status != "VERIFIED":
        return JsonResponse({"ok": False, "message": "Admin verification is required first."}, status=403)
    action = str(_payload(request).get("action", "")).lower()
    if action not in {"confirm", "cancel"}:
        return JsonResponse({"ok": False, "message": "Choose confirm or cancel."}, status=400)
    with transaction.atomic():
        try:
            booking = Booking.objects.select_for_update().select_related("vehicle").get(
                pk=booking_id, vehicle__shopkeeper=profile
            )
        except Booking.DoesNotExist:
            return JsonResponse({"ok": False, "message": "Booking not found for this shop."}, status=404)
        if booking.status in {Booking.Status.CANCELLED, Booking.Status.COMPLETED}:
            return JsonResponse({"ok": False, "message": "This booking can no longer be changed."}, status=409)
        booking.status = Booking.Status.CONFIRMED if action == "confirm" else Booking.Status.CANCELLED
        booking.save(update_fields=["status", "updated_at"])
        AuditLog.objects.create(
            actor=request.user,
            action=f"booking_{action}",
            entity_type="booking",
            entity_id=booking.id,
            metadata={"vehicle_id": booking.vehicle_id, "customer_id": booking.customer_id},
        )
    return JsonResponse({"ok": True, "message": f"Booking {'confirmed' if action == 'confirm' else 'cancelled'} successfully."})


@login_required
@require_POST
def shopkeeper_vehicle_availability(request, vehicle_id):
    """Toggle a verified shopkeeper's vehicle without changing its listing approval."""
    if request.user.role != User.Role.SHOPKEEPER:
        return JsonResponse({"ok": False, "message": "Shopkeeper access only."}, status=403)
    profile = getattr(request.user, "shopkeeper_profile", None)
    if not profile or profile.verification_status != "VERIFIED":
        return JsonResponse({"ok": False, "message": "Admin verification is required first."}, status=403)
    with transaction.atomic():
        try:
            vehicle = Vehicle.objects.select_for_update().get(pk=vehicle_id, shopkeeper=profile)
        except Vehicle.DoesNotExist:
            return JsonResponse({"ok": False, "message": "Vehicle not found for this shop."}, status=404)
        vehicle.is_available = not vehicle.is_available
        vehicle.save(update_fields=["is_available", "updated_at"])
        AuditLog.objects.create(
            actor=request.user,
            action="vehicle_availability_changed",
            entity_type="vehicle",
            entity_id=vehicle.id,
            metadata={"is_available": vehicle.is_available},
        )
    return JsonResponse({"ok": True, "message": f"Vehicle marked {'available' if vehicle.is_available else 'unavailable'}."})
