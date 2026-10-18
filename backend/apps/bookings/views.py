import json
from datetime import timedelta
import re

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import User
from apps.payments.models import PaymentTransaction
from apps.adminpanel.models import AuditLog
from apps.vehicles.models import Vehicle
from .models import Booking
from .handover import HANDOVER_CODE_TTL_MINUTES, issue_handover_code
from .services import create_checkout_booking, create_locked_booking, expire_checkout_holds
from apps.accounts.models import phone_validator
from apps.verification.services import validate_aadhaar


def _payload(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}


def _booking_summary(booking):
    """Return a customer-safe complete receipt for history and success views."""
    payment = getattr(booking, "payment", None)
    vehicle = booking.vehicle
    return {
        "id": booking.id,
        "vehicle": vehicle.display_name,
        "vehicle_type": vehicle.vehicle_type,
        "vehicle_image": vehicle.image.url if vehicle.image else "",
        "shop": vehicle.shopkeeper.shop_name,
        "shop_address": vehicle.shopkeeper.shop_address,
        "pickup_date": booking.pickup_date.isoformat(),
        "return_date": booking.return_date.isoformat(),
        "status": booking.status,
        "total_amount": str(booking.total_amount),
        "renter_name": booking.renter_full_name,
        "renter_age": booking.renter_age,
        "renter_gender": booking.renter_gender,
        "renter_phone": booking.renter_phone,
        "renter_email": booking.renter_email,
        "identity_verified": hasattr(booking, "identity_verification"),
        "payment_expires_at": booking.payment_expires_at.isoformat() if booking.payment_expires_at else None,
        "payment_hold_expired": bool(booking.status == Booking.Status.CANCELLED and booking.payment_expires_at and booking.payment_expires_at <= timezone.now()),
        "payment": {
            "status": payment.status if payment else "CANCELLED",
            "amount": str(payment.amount) if payment else str(booking.total_amount),
            "currency": payment.currency if payment else "INR",
            "provider": payment.provider if payment and payment.provider else "Online payment",
            "reference": payment.provider_payment_id if payment and payment.provider_payment_id else "Will appear after payment confirmation",
        },
    }


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
    return JsonResponse({
        "ok": True,
        "message": "Booking request created safely.",
        "booking_id": booking.id,
        "payment_id": payment.id,
        "total_amount": str(booking.total_amount),
        "payment_expires_at": booking.payment_expires_at.isoformat() if booking.payment_expires_at else None,
        "payment_hold_minutes": 10,
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
    return JsonResponse({
        "ok": True,
        "message": "Your booking request is saved. Complete the secure payment to send it for shop review.",
        "booking_id": booking.id,
        "payment_id": payment.id,
        "total_amount": str(booking.total_amount),
        "status": booking.status,
        "payment_expires_at": booking.payment_expires_at.isoformat() if booking.payment_expires_at else None,
        "payment_hold_minutes": 10,
        "payment_test_mode": settings.RAZORPAY_KEY_ID.startswith("rzp_test_"),
    })


@login_required
@require_GET
def checkout_defaults(request):
    """Return the last renter details for convenient, editable repeat checkout."""
    if request.user.role != User.Role.USER:
        return JsonResponse({"ok": False, "message": "Customer access only."}, status=403)
    last_booking = (
        Booking.objects.filter(customer=request.user, renter_age__isnull=False)
        .exclude(renter_gender="")
        .order_by("-created_at")
        .first()
    )
    return JsonResponse({
        "ok": True,
        "defaults": {
            "full_name": last_booking.renter_full_name if last_booking else request.user.get_full_name(),
            "age": last_booking.renter_age if last_booking else None,
            "gender": last_booking.renter_gender if last_booking else "",
            "phone": last_booking.renter_phone if last_booking else request.user.phone_number,
            "email": request.user.email,
        },
    })


@login_required
@require_POST
def request_handover_code(request, booking_id):
    """Issue a one-time pickup/return code only to the authenticated renter."""
    if request.user.role != User.Role.USER:
        return JsonResponse({"ok": False, "message": "Customer access only."}, status=403)
    stage = str(_payload(request).get("stage") or "").upper()
    try:
        issued = issue_handover_code(customer=request.user, booking_id=booking_id, stage=stage)
    except LookupError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=404)
    except TimeoutError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=429)
    except ValueError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=409)
    return JsonResponse({
        "ok": True,
        "stage": stage,
        "code": issued["code"],
        "expires_at": issued["expires_at"].isoformat(),
        "expires_in_seconds": HANDOVER_CODE_TTL_MINUTES * 60,
        "message": "Share this one-time code with your shopkeeper in person. It expires in 10 minutes.",
    })


@login_required
@require_GET
def booking_history(request):
    if request.user.role != User.Role.USER:
        return JsonResponse({"ok": False, "message": "Customer access only."}, status=403)
    expire_checkout_holds()
    bookings = Booking.objects.filter(customer=request.user).select_related("vehicle", "vehicle__shopkeeper", "payment")
    return JsonResponse({
        "ok": True,
        "bookings": [
            _booking_summary(booking)
            for booking in bookings
        ],
    })


@login_required
@require_POST
def cancel_customer_booking(request, booking_id):
    if request.user.role != User.Role.USER:
        return JsonResponse({"ok": False, "message": "Customer access only."}, status=403)
    with transaction.atomic():
        try:
            booking = Booking.objects.select_for_update().select_related("vehicle", "vehicle__shopkeeper").get(pk=booking_id, customer=request.user)
        except Booking.DoesNotExist:
            return JsonResponse({"ok": False, "message": "Booking not found."}, status=404)
        payment = PaymentTransaction.objects.select_for_update().filter(booking=booking).first()
        if booking.status != Booking.Status.PENDING:
            return JsonResponse({"ok": False, "message": "Only a pending booking can be cancelled here."}, status=409)
        if payment and payment.status == PaymentTransaction.Status.PAID:
            return JsonResponse({"ok": False, "message": "This booking has a verified payment. Contact support for the refund process."}, status=409)
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status", "updated_at"])
        if payment and payment.status == PaymentTransaction.Status.PENDING:
            payment.status = PaymentTransaction.Status.CANCELLED
            payment.save(update_fields=["status", "updated_at"])
    return JsonResponse({"ok": True, "message": "Booking cancelled. No payment was collected."})


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
        if booking.status != Booking.Status.PENDING:
            return JsonResponse({"ok": False, "message": "This booking has already been processed."}, status=409)
        payment = PaymentTransaction.objects.select_for_update().filter(booking=booking).first()
        if action == "confirm" and (not payment or payment.status != PaymentTransaction.Status.PAID):
            return JsonResponse({"ok": False, "message": "Confirm the booking only after its payment is verified."}, status=409)
        if action == "cancel" and payment and payment.status == PaymentTransaction.Status.PAID:
            return JsonResponse({"ok": False, "message": "A paid booking requires a refund through support before it can be cancelled."}, status=409)
        booking.status = Booking.Status.CONFIRMED if action == "confirm" else Booking.Status.CANCELLED
        if action == "cancel" and payment and payment.status == PaymentTransaction.Status.PENDING:
            payment.status = PaymentTransaction.Status.CANCELLED
            payment.save(update_fields=["status", "updated_at"])
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
