import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import User
from .models import Booking
from .services import create_locked_booking


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
            }
            for booking in bookings
        ],
    })
