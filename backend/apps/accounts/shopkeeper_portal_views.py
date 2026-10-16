"""Authenticated operations for the shopkeeper workspace."""

import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.bookings.models import Booking
from apps.payments.models import PaymentTransaction
from apps.vehicles.models import Vehicle
from .models import ShopkeeperProfile, User


def _payload(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}


def _shopkeeper_only(view):
    @login_required
    def wrapped(request, *args, **kwargs):
        if request.user.role != User.Role.SHOPKEEPER:
            return JsonResponse({"ok": False, "message": "Shopkeeper access only."}, status=403)
        profile = getattr(request.user, "shopkeeper_profile", None)
        if not profile or profile.verification_status == ShopkeeperProfile.VerificationStatus.REVOKED:
            return JsonResponse({"ok": False, "message": "This shopkeeper account is unavailable."}, status=403)
        return view(request, profile, *args, **kwargs)
    return wrapped


@_shopkeeper_only
@require_GET
def shopkeeper_summary(request, profile):
    vehicles = profile.vehicles.all()
    paid_bookings = Booking.objects.filter(
        vehicle__shopkeeper=profile,
        payment__status=PaymentTransaction.Status.PAID,
    )
    paid = PaymentTransaction.objects.filter(booking__in=paid_bookings)
    return JsonResponse({"ok": True, "profile": {"shop_name": profile.shop_name, "shop_address": profile.shop_address, "shop_description": profile.shop_description, "latitude": str(profile.latitude or ""), "longitude": str(profile.longitude or ""), "verification_status": profile.verification_status, "email": request.user.email, "phone": request.user.phone_number}, "summary": {
        "total_vehicles": vehicles.count(),
        "approved_vehicles": vehicles.filter(listing_status=Vehicle.ListingStatus.APPROVED).count(),
        "available_vehicles": vehicles.filter(listing_status=Vehicle.ListingStatus.APPROVED, is_available=True).count(),
        "pending_reservations": paid_bookings.filter(status=Booking.Status.PENDING).count(),
        "paid_awaiting_action": paid_bookings.filter(status=Booking.Status.PENDING).count(),
        "paid_bookings": paid.count(),
        "gross_earnings": paid.aggregate(total=Sum("amount"))["total"] or 0,
    }})


@_shopkeeper_only
@require_GET
def shopkeeper_reservations(request, profile):
    # A shop sees only completed online payments. Pending, failed and cancelled
    # checkout attempts stay private to the customer and remain available to admins.
    bookings = Booking.objects.filter(
        vehicle__shopkeeper=profile,
        payment__status=PaymentTransaction.Status.PAID,
    ).select_related("customer", "vehicle", "payment")[:100]
    rows = []
    for booking in bookings:
        rows.append({"id": booking.id, "vehicle": booking.vehicle.display_name, "customer": booking.customer.get_full_name() or booking.customer.email, "customer_email": booking.customer.email, "customer_phone": booking.customer.phone_number, "pickup_date": booking.pickup_date.isoformat(), "return_date": booking.return_date.isoformat(), "total_amount": str(booking.total_amount), "status": booking.status, "payment_status": booking.payment.status, "created_at": booking.created_at.isoformat()})
    return JsonResponse({"ok": True, "reservations": rows})


@_shopkeeper_only
@require_POST
def shopkeeper_reservation_action(request, profile, booking_id):
    if profile.verification_status != ShopkeeperProfile.VerificationStatus.VERIFIED:
        return JsonResponse({"ok": False, "message": "One-time admin verification is required before managing reservations."}, status=403)
    action = str(_payload(request).get("action") or "").upper()
    if action not in {"CONFIRM", "DECLINE"}:
        return JsonResponse({"ok": False, "message": "Choose a valid reservation action."}, status=400)
    try:
        with transaction.atomic():
            booking = Booking.objects.select_for_update().select_related("customer", "vehicle").get(pk=booking_id, vehicle__shopkeeper=profile)
            if booking.status != Booking.Status.PENDING:
                return JsonResponse({"ok": False, "message": "This reservation has already been processed."}, status=409)
            payment = PaymentTransaction.objects.select_for_update().filter(booking=booking).first()
            payment_status = payment.status if payment else PaymentTransaction.Status.PENDING
            if action == "CONFIRM":
                if payment_status != PaymentTransaction.Status.PAID:
                    return JsonResponse({"ok": False, "message": "Confirm the reservation only after its payment is verified."}, status=409)
                booking.status = Booking.Status.CONFIRMED
            else:
                if payment_status == PaymentTransaction.Status.PAID:
                    return JsonResponse({"ok": False, "message": "This reservation has a verified payment. Contact support so a refund can be handled safely."}, status=409)
                booking.status = Booking.Status.CANCELLED
                if payment and payment.status == PaymentTransaction.Status.PENDING:
                    payment.status = PaymentTransaction.Status.CANCELLED
                    payment.save(update_fields=["status", "updated_at"])
            booking.save(update_fields=["status", "updated_at"])
    except Booking.DoesNotExist:
        return JsonResponse({"ok": False, "message": "Reservation not found."}, status=404)
    return JsonResponse({"ok": True, "message": "Reservation confirmed." if action == "CONFIRM" else "Reservation declined safely."})


@_shopkeeper_only
@require_POST
def set_vehicle_availability(request, profile, vehicle_id):
    if profile.verification_status != ShopkeeperProfile.VerificationStatus.VERIFIED:
        return JsonResponse({"ok": False, "message": "One-time admin verification is required before managing vehicle availability."}, status=403)
    available = _payload(request).get("is_available")
    if not isinstance(available, bool):
        return JsonResponse({"ok": False, "message": "Choose a valid availability value."}, status=400)
    try:
        with transaction.atomic():
            vehicle = Vehicle.objects.select_for_update().get(pk=vehicle_id, shopkeeper=profile)
            if vehicle.listing_status != Vehicle.ListingStatus.APPROVED:
                return JsonResponse({"ok": False, "message": "Only approved listings can have availability changed."}, status=409)
            if not available and Booking.objects.filter(vehicle=vehicle, status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED], return_date__gte=timezone.localdate()).exists():
                return JsonResponse({"ok": False, "message": "This vehicle has a current or upcoming reservation. Resolve it before marking unavailable."}, status=409)
            vehicle.is_available = available
            vehicle.save(update_fields=["is_available", "updated_at"])
    except Vehicle.DoesNotExist:
        return JsonResponse({"ok": False, "message": "Vehicle not found."}, status=404)
    return JsonResponse({"ok": True, "message": "Vehicle is now available for search." if available else "Vehicle is now unavailable for new searches."})


@_shopkeeper_only
@require_POST
def update_vehicle_rate(request, profile, vehicle_id):
    if profile.verification_status != ShopkeeperProfile.VerificationStatus.VERIFIED:
        return JsonResponse({"ok": False, "message": "One-time admin verification is required before changing fares."}, status=403)
    try:
        daily_rate = Decimal(str(_payload(request).get("daily_rate", "")))
    except (InvalidOperation, ValueError):
        return JsonResponse({"ok": False, "message": "Enter a valid daily rate."}, status=400)
    if daily_rate < 0 or daily_rate >= Decimal("100000000"):
        return JsonResponse({"ok": False, "message": "Enter a daily rate within the allowed range."}, status=400)
    try:
        vehicle = Vehicle.objects.get(pk=vehicle_id, shopkeeper=profile, listing_status=Vehicle.ListingStatus.APPROVED)
    except Vehicle.DoesNotExist:
        return JsonResponse({"ok": False, "message": "Only your approved vehicles can have fares changed."}, status=404)
    vehicle.daily_rate = daily_rate
    vehicle.save(update_fields=["daily_rate", "updated_at"])
    return JsonResponse({"ok": True, "message": "Daily fare updated successfully."})
