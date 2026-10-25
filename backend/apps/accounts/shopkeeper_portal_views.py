"""Authenticated operations for the shopkeeper workspace."""

import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.bookings.handover import record_handover_inspection
from apps.bookings.models import Booking, BookingInspection
from apps.bookings.services import active_reservation_filter
from apps.bookings.finance import reverse_booking_commission
from apps.payments.models import PaymentTransaction
from apps.vehicles.models import Vehicle
from apps.notifications.services import notify_user
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
    return JsonResponse({"ok": True, "profile": {"shop_name": profile.shop_name, "shop_address": profile.shop_address, "shop_description": profile.shop_description, "latitude": str(profile.latitude or ""), "longitude": str(profile.longitude or ""), "verification_status": profile.verification_status, "compliance_complete": profile.is_compliance_complete, "legal_business_name": profile.legal_business_name, "proprietor_name": profile.proprietor_name, "business_type": profile.business_type, "gstin": profile.gstin, "pan_number": profile.pan_number, "aadhaar_last4": profile.aadhaar_last4, "business_registration_number": profile.business_registration_number, "email": request.user.email, "phone": request.user.phone_number}, "summary": {
        "total_vehicles": vehicles.count(),
        "approved_vehicles": vehicles.filter(listing_status=Vehicle.ListingStatus.APPROVED).count(),
        "available_vehicles": vehicles.filter(listing_status=Vehicle.ListingStatus.APPROVED, is_available=True).count(),
        "pending_reservations": paid_bookings.filter(status=Booking.Status.CONFIRMED).count(),
        "paid_awaiting_action": paid_bookings.filter(status=Booking.Status.CONFIRMED).count(),
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
@require_GET
def shopkeeper_earnings(request, profile):
    """Financial snapshots for this shop only; URL parameters cannot widen scope."""
    rows = Booking.objects.filter(
        vehicle__shopkeeper=profile, payment__status__in=[PaymentTransaction.Status.PAID, PaymentTransaction.Status.REFUNDED],
        financial_confirmed_at__isnull=False,
    ).select_related("customer", "vehicle", "payment").order_by("-created_at")
    if request.GET.get("vehicle_id"):
        rows = rows.filter(vehicle_id=request.GET["vehicle_id"])
    if request.GET.get("booking_status"):
        rows = rows.filter(status=request.GET["booking_status"])
    if request.GET.get("payment_status"):
        rows = rows.filter(payment__status=request.GET["payment_status"])
    if request.GET.get("date_from"):
        rows = rows.filter(created_at__date__gte=request.GET["date_from"])
    if request.GET.get("date_to"):
        rows = rows.filter(created_at__date__lte=request.GET["date_to"])
    term = request.GET.get("q", "").strip()
    if term:
        rows = rows.filter(Q(pk__icontains=term) | Q(vehicle__brand__icontains=term) | Q(vehicle__model_name__icontains=term))
    realized = rows.filter(payment__status=PaymentTransaction.Status.PAID, commission_reversed_at__isnull=True)
    totals = realized.aggregate(gross=Sum("commissionable_base"), commission=Sum("platform_commission"), net=Sum("shopkeeper_net_earnings"), count=Sum("id"))
    page = Paginator(rows, 25).get_page(request.GET.get("page", 1))
    def serialize(item):
        return {"id": item.id, "reference": f"RH-{item.id:06d}", "booking_date": item.created_at.isoformat(), "vehicle": item.vehicle.display_name, "vehicle_image": item.vehicle.image.url if item.vehicle.image else "", "customer": item.customer.get_full_name() or item.customer.email, "pickup_date": item.pickup_date.isoformat(), "return_date": item.return_date.isoformat(), "commissionable_base": str(item.commissionable_base), "commission_rate": str(item.commission_rate), "platform_commission": str(item.platform_commission), "net_earnings": str(item.shopkeeper_net_earnings), "payment_status": item.payment.status, "booking_status": item.status, "reversed": bool(item.commission_reversed_at)}
    return JsonResponse({"ok": True, "summary": {"eligible_rental_fare": str(totals["gross"] or 0), "commission_deducted": str(totals["commission"] or 0), "net_earnings": str(totals["net"] or 0), "eligible_bookings": realized.count(), "pending_payments": Booking.objects.filter(vehicle__shopkeeper=profile, payment__status=PaymentTransaction.Status.PENDING).count(), "note": "Computed earnings are not a settlement or payout."}, "rows": [serialize(item) for item in page.object_list], "pagination": {"page": page.number, "pages": page.paginator.num_pages}})


@_shopkeeper_only
@require_POST
def shopkeeper_reservation_action(request, profile, booking_id):
    if profile.verification_status != ShopkeeperProfile.VerificationStatus.VERIFIED:
        return JsonResponse({"ok": False, "message": "One-time admin verification is required before managing reservations."}, status=403)
    payload = _payload(request)
    action = str(payload.get("action") or "").upper()
    if action not in {"TAKEOVER", "RECEIVED_BACK", "CANCEL"}:
        return JsonResponse({"ok": False, "message": "Choose vehicle takeover, received back, or cancellation."}, status=400)
    if action in {"TAKEOVER", "RECEIVED_BACK"}:
        stage = BookingInspection.Stage.PICKUP if action == "TAKEOVER" else BookingInspection.Stage.RETURN
        try:
            record_handover_inspection(
                profile=profile,
                booking_id=booking_id,
                stage=stage,
                code=payload.get("code"),
                payload=payload,
            )
        except LookupError as exc:
            return JsonResponse({"ok": False, "message": str(exc)}, status=404)
        except ValueError as exc:
            return JsonResponse({"ok": False, "message": str(exc)}, status=409)
        message = "Pickup inspection recorded and vehicle handed over." if stage == BookingInspection.Stage.PICKUP else "Return inspection recorded and ride completed."
        return JsonResponse({"ok": True, "message": message})

    try:
        with transaction.atomic():
            booking = Booking.objects.select_for_update().select_related("customer", "vehicle").get(pk=booking_id, vehicle__shopkeeper=profile)
            if action == "CANCEL" and booking.status not in {Booking.Status.CONFIRMED, Booking.Status.HANDED_OVER}:
                return JsonResponse({"ok": False, "message": "This booking cannot be cancelled at its current stage."}, status=409)
            payment = PaymentTransaction.objects.select_for_update().filter(booking=booking).first()
            reason = " ".join(str(payload.get("reason") or "").split())
            if len(reason) < 5:
                return JsonResponse({"ok": False, "message": "Give the customer a clear cancellation reason."}, status=400)
            booking.status = Booking.Status.CANCELLED
            booking.shopkeeper_cancellation_reason = reason[:1000]
            if payment and payment.status == PaymentTransaction.Status.PAID:
                # Gateway implementation is selected through the payment adapter.
                from apps.payments.gateways import get_payment_gateway
                try:
                    gateway = get_payment_gateway(payment.provider or "RAZORPAY")
                    gateway.refund(payment.provider_payment_id, {"amount": int(payment.amount * 100), "notes": {"booking_id": str(booking.id), "reason": reason[:100]}})
                except Exception:
                    return JsonResponse({"ok": False, "message": "Refund could not be initiated safely. Please try again or contact RideHub support."}, status=502)
                payment.status = PaymentTransaction.Status.REFUNDED
                payment.save(update_fields=["status", "updated_at"])
                reverse_booking_commission(booking)
            booking.save(update_fields=["status", "handover_at", "received_back_at", "shopkeeper_cancellation_reason", "updated_at"])
    except Booking.DoesNotExist:
        return JsonResponse({"ok": False, "message": "Reservation not found."}, status=404)
    labels = {"CANCEL": "Booking cancelled and refund initiated automatically."}
    if action == "CANCEL":
        notify_user(booking.customer, "Ride cancelled — refund initiated", f"Your {booking.vehicle.display_name} booking was cancelled by the shop. Reason: {booking.shopkeeper_cancellation_reason}. Your refund has been initiated.")
    return JsonResponse({"ok": True, "message": labels[action]})


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
            if not available and Booking.objects.filter(vehicle=vehicle, return_date__gte=timezone.localdate()).filter(active_reservation_filter()).exists():
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
