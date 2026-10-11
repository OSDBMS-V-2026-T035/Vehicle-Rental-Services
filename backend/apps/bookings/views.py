import json
from datetime import timedelta
import re

from django.contrib.auth.decorators import login_required
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import User
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
    return JsonResponse({
        "ok": True,
        "message": "Booking request created safely.",
        "booking_id": booking.id,
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
    return JsonResponse({
        "ok": True,
        "message": "Your booking request is saved. Payment will be added in the next step.",
        "booking_id": booking.id,
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
