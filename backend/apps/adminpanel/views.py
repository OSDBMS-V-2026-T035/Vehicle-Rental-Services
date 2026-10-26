import json
from decimal import Decimal, InvalidOperation
from datetime import date

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.accounts.models import ShopkeeperProfile, User
from apps.notifications.services import notify_user
from apps.bookings.models import Booking
from apps.payments.models import PaymentTransaction
from .models import AuditLog
from apps.vehicles.models import Vehicle


def _admin_only(view):
    @login_required
    def wrapped(request, *args, **kwargs):
        if request.user.role != User.Role.ADMIN or not request.user.is_staff:
            return JsonResponse({"ok": False, "message": "Administrator access only."}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


def _payload(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}


@_admin_only
def dashboard(request):
    pending_shops = ShopkeeperProfile.objects.filter(
        verification_status=ShopkeeperProfile.VerificationStatus.PENDING
    ).select_related("user")
    shopkeepers = ShopkeeperProfile.objects.select_related("user").annotate(vehicle_count=Count("vehicles"))
    pending_vehicles = Vehicle.objects.filter(
        listing_status=Vehicle.ListingStatus.PENDING
    ).select_related("shopkeeper", "shopkeeper__user")
    users = User.objects.filter(role=User.Role.USER).order_by("-created_at")
    bookings = Booking.objects.select_related("customer", "vehicle", "vehicle__shopkeeper").order_by("-created_at")[:25]
    audit_logs = AuditLog.objects.select_related("actor").order_by("-created_at")[:20]
    stats = {
        "pending_shops": pending_shops.count(),
        "pending_vehicles": pending_vehicles.count(),
        "users": User.objects.filter(role=User.Role.USER).count(),
        "verified_shops": ShopkeeperProfile.objects.filter(
            verification_status=ShopkeeperProfile.VerificationStatus.VERIFIED
        ).count(),
        "active_bookings": Booking.objects.filter(status=Booking.Status.CONFIRMED).count(),
        "total_bookings": Booking.objects.count(),
        "revenue": Booking.objects.filter(
            status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED, Booking.Status.COMPLETED]
        ).aggregate(total=Sum("total_amount"))["total"] or 0,
    }
    return render(request, "admin_dashboard.html", {
        "stats": stats,
        "pending_shops": pending_shops,
        "shopkeepers": shopkeepers,
        "pending_vehicles": pending_vehicles,
        "users": users,
        "bookings": bookings,
        "audit_logs": audit_logs,
    })


@_admin_only
@require_POST
def shopkeeper_action(request, profile_id):
    profile = get_object_or_404(ShopkeeperProfile.objects.select_related("user"), pk=profile_id)
    action = _payload(request).get("action", "").lower()
    status_by_action = {
        "approve": ShopkeeperProfile.VerificationStatus.VERIFIED,
        "reject": ShopkeeperProfile.VerificationStatus.REJECTED,
        "revoke": ShopkeeperProfile.VerificationStatus.REVOKED,
        "permanent_ban": ShopkeeperProfile.VerificationStatus.REVOKED,
    }
    if action == "edit":
        payload = _payload(request)
        name = " ".join(str(payload.get("shop_name", "")).split())
        address = " ".join(str(payload.get("shop_address", "")).split())
        description = " ".join(str(payload.get("shop_description", "")).split())
        if len(name) < 2 or len(address) < 8:
            return JsonResponse({"ok": False, "message": "Enter a shop name and complete address."}, status=400)
        try:
            latitude = Decimal(str(payload.get("latitude", ""))) if payload.get("latitude") else None
            longitude = Decimal(str(payload.get("longitude", ""))) if payload.get("longitude") else None
        except (InvalidOperation, ValueError):
            return JsonResponse({"ok": False, "message": "Enter valid location coordinates."}, status=400)
        if (latitude is None) != (longitude is None) or (latitude is not None and not (-90 <= latitude <= 90 and -180 <= longitude <= 180)):
            return JsonResponse({"ok": False, "message": "Enter a valid current latitude and longitude together."}, status=400)
        profile.shop_name, profile.shop_address, profile.shop_description = name, address, description
        profile.latitude, profile.longitude = latitude, longitude
        profile.save(update_fields=["shop_name", "shop_address", "shop_description", "latitude", "longitude", "updated_at"])
        AuditLog.objects.create(actor=request.user, action="shopkeeper_edited", entity_type="shopkeeper", entity_id=profile.id)
        return JsonResponse({"ok": True, "message": "Shopkeeper details updated."})
    if action == "delete":
        with transaction.atomic():
            # Preserve bookings, payments and audit evidence.  A financial
            # account is deactivated rather than erased from the system.
            profile.verification_status = ShopkeeperProfile.VerificationStatus.REVOKED
            profile.user.is_active = False
            profile.user.save(update_fields=["is_active", "updated_at"])
            profile.save(update_fields=["verification_status", "updated_at"])
            AuditLog.objects.create(actor=request.user, action="shopkeeper_deactivated", entity_type="shopkeeper", entity_id=profile.id)
        return JsonResponse({"ok": True, "message": "Shopkeeper account deactivated; booking and payment history was preserved."})
    if action not in status_by_action:
        return JsonResponse({"ok": False, "message": "Choose approve, reject, revoke, edit, or delete."}, status=400)
    if action == "approve" and profile.user.is_permanently_banned:
        return JsonResponse({"ok": False, "message": "A permanently banned shopkeeper cannot be re-approved."}, status=409)
    if action == "approve" and not profile.is_compliance_complete:
        return JsonResponse({"ok": False, "message": "Review cannot be approved until all mandatory shopkeeper compliance details and documents are submitted."}, status=409)
    with transaction.atomic():
        profile.verification_status = status_by_action[action]
        profile.user.is_active = action != "revoke"
        if action == "permanent_ban":
            profile.user.is_active = False
            profile.user.is_permanently_banned = True
        profile.user.save(update_fields=["is_active", "is_permanently_banned", "updated_at"])
        profile.save(update_fields=["verification_status", "updated_at"])
        AuditLog.objects.create(actor=request.user, action=f"shopkeeper_{action}", entity_type="shopkeeper", entity_id=profile.id, metadata={"email": profile.user.email})
    label = {"approve": "approved", "reject": "rejected", "revoke": "revoked", "permanent_ban": "permanently banned"}[action]
    notify_user(profile.user, f"Shopkeeper account {label}", f"Your shopkeeper account for {profile.shop_name} was {label} by the RideHub review team.")
    return JsonResponse({"ok": True, "message": f"Shopkeeper {label} successfully."})


@_admin_only
@require_POST
def vehicle_action(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
    action = _payload(request).get("action", "").lower()
    if action == "edit":
        payload = _payload(request)
        try:
            rate = float(payload.get("daily_rate"))
            quantity = int(payload.get("quantity"))
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "message": "Enter a valid rate and quantity."}, status=400)
        if rate < 0 or not 1 <= quantity <= 999:
            return JsonResponse({"ok": False, "message": "Rate must be positive and quantity must be 1–999."}, status=400)
        vehicle.daily_rate = rate
        vehicle.quantity = quantity
        vehicle.available_quantity = min(vehicle.available_quantity, quantity)
        vehicle.save(update_fields=["daily_rate", "quantity", "available_quantity", "updated_at"])
        AuditLog.objects.create(actor=request.user, action="vehicle_edited", entity_type="vehicle", entity_id=vehicle.id)
        return JsonResponse({"ok": True, "message": "Vehicle rate and inventory updated."})
    if action == "delete":
        with transaction.atomic():
            vehicle.is_available = False
            vehicle.listing_status = Vehicle.ListingStatus.REJECTED
            vehicle.admin_note = "Archived by RideHub administration."
            vehicle.save(update_fields=["is_available", "listing_status", "admin_note", "updated_at"])
            AuditLog.objects.create(actor=request.user, action="vehicle_archived", entity_type="vehicle", entity_id=vehicle.id)
        return JsonResponse({"ok": True, "message": "Vehicle archived; booking and payment history was preserved."})
    if action not in {"approve", "reject"}:
        return JsonResponse({"ok": False, "message": "Choose approve, reject, edit, or delete."}, status=400)
    if action == "approve" and vehicle.shopkeeper.verification_status != ShopkeeperProfile.VerificationStatus.VERIFIED:
        return JsonResponse({"ok": False, "message": "Verify the shopkeeper before approving a vehicle."}, status=409)
    with transaction.atomic():
        vehicle.listing_status = Vehicle.ListingStatus.APPROVED if action == "approve" else Vehicle.ListingStatus.REJECTED
        vehicle.is_available = action == "approve"
        vehicle.admin_note = str(_payload(request).get("note", "")).strip()[:255]
        vehicle.save(update_fields=["listing_status", "is_available", "admin_note", "updated_at"])
        AuditLog.objects.create(actor=request.user, action=f"vehicle_{action}", entity_type="vehicle", entity_id=vehicle.id, metadata={"registration_number": vehicle.registration_number})
    notify_user(vehicle.shopkeeper.user, f"Vehicle listing {action}d", f"Your {vehicle.display_name} listing was {action}d by the RideHub review team.")
    return JsonResponse({"ok": True, "message": f"Vehicle {'approved' if action == 'approve' else 'rejected'} successfully."})


@_admin_only
@require_POST
def user_action(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if user == request.user:
        return JsonResponse({"ok": False, "message": "You cannot revoke your own admin account."}, status=400)
    action = _payload(request).get("action", "").lower()
    if action == "edit":
        payload = _payload(request)
        name = " ".join(str(payload.get("full_name", "")).split())
        if not name:
            return JsonResponse({"ok": False, "message": "Enter the customer's name."}, status=400)
        first, *rest = name.split(" ", 1)
        phone = "".join(str(payload.get("phone", user.phone_number)).split())
        if phone != user.phone_number:
            from apps.accounts.models import phone_validator
            try:
                phone_validator(phone)
            except ValidationError as exc:
                return JsonResponse({"ok": False, "message": exc.messages[0]}, status=400)
            if User.objects.exclude(pk=user.pk).filter(phone_number=phone).exists():
                return JsonResponse({"ok": False, "message": "This mobile number is already in use."}, status=409)
        user.first_name, user.last_name, user.phone_number = first, rest[0] if rest else "", phone
        user.save(update_fields=["first_name", "last_name", "phone_number", "updated_at"])
        AuditLog.objects.create(actor=request.user, action="user_edited", entity_type="user", entity_id=user.id)
        return JsonResponse({"ok": True, "message": "Customer details updated."})
    if action == "delete":
        with transaction.atomic():
            user.is_active = False
            user.save(update_fields=["is_active", "updated_at"])
            AuditLog.objects.create(actor=request.user, action="user_deactivated", entity_type="user", entity_id=user.id)
        return JsonResponse({"ok": True, "message": "Customer account deactivated; booking and payment history was preserved."})
    if action not in {"revoke", "restore", "permanent_ban"}:
        return JsonResponse({"ok": False, "message": "Choose revoke, restore, edit, or delete."}, status=400)
    if action == "restore" and user.is_permanently_banned:
        return JsonResponse({"ok": False, "message": "A permanently banned account cannot be restored."}, status=409)
    with transaction.atomic():
        user.is_active = action == "restore"
        if action == "permanent_ban":
            user.is_active = False
            user.is_permanently_banned = True
        user.save(update_fields=["is_active", "is_permanently_banned", "updated_at"])
        AuditLog.objects.create(actor=request.user, action=f"user_{action}", entity_type="user", entity_id=user.id, metadata={"email": user.email})
    notification_label = "permanently banned" if action == "permanent_ban" else f"{action}d"
    notify_user(user, f"Account {notification_label}", f"Your RideHub account was {notification_label} by the platform administration team.")
    label = "restored" if action == "restore" else ("permanently banned" if action == "permanent_ban" else "revoked")
    return JsonResponse({"ok": True, "message": f"User {label} successfully."})


@_admin_only
@require_POST
def booking_action(request, booking_id):
    action = _payload(request).get("action", "").lower()
    if action == "delete":
        return JsonResponse({"ok": False, "message": "Bookings are financial records and cannot be deleted. Use the audited cancellation workflow where applicable."}, status=409)
    if action not in {"confirm", "cancel", "complete", "edit"}:
        return JsonResponse({"ok": False, "message": "Choose confirm, cancel, complete, edit, or delete."}, status=400)
    status_by_action = {
        "confirm": Booking.Status.CONFIRMED,
        "cancel": Booking.Status.CANCELLED,
        "complete": Booking.Status.COMPLETED,
    }
    with transaction.atomic():
        try:
            booking = Booking.objects.select_for_update().get(pk=booking_id)
        except Booking.DoesNotExist:
            return JsonResponse({"ok": False, "message": "Booking not found."}, status=404)
        if booking.status == Booking.Status.COMPLETED and action != "complete":
            return JsonResponse({"ok": False, "message": "A completed booking cannot be changed."}, status=409)
        payment = PaymentTransaction.objects.select_for_update().filter(booking=booking).first()
        if action == "edit":
            payload = _payload(request)
            try:
                pickup = date.fromisoformat(str(payload.get("pickup_date")))
                return_date = date.fromisoformat(str(payload.get("return_date")))
            except (TypeError, ValueError):
                return JsonResponse({"ok": False, "message": "Use valid pickup and return dates."}, status=400)
            if payment and payment.status == PaymentTransaction.Status.PAID:
                return JsonResponse({"ok": False, "message": "Paid booking dates cannot be edited."}, status=409)
            if return_date < pickup:
                return JsonResponse({"ok": False, "message": "Return date must be after pickup."}, status=400)
            booking.pickup_date, booking.return_date = pickup, return_date
            booking.save(update_fields=["pickup_date", "return_date", "updated_at"])
            AuditLog.objects.create(actor=request.user, action="admin_booking_edited", entity_type="booking", entity_id=booking.id)
            return JsonResponse({"ok": True, "message": "Booking dates updated."})
        if action == "confirm" and (not payment or payment.status != PaymentTransaction.Status.PAID):
            return JsonResponse({"ok": False, "message": "Only paid bookings can be confirmed."}, status=409)
        if action == "cancel" and payment and payment.status == PaymentTransaction.Status.PAID:
            return JsonResponse({"ok": False, "message": "A paid booking requires a refund before cancellation."}, status=409)
        booking.status = status_by_action[action]
        booking.save(update_fields=["status", "updated_at"])
        if action == "cancel" and payment and payment.status == PaymentTransaction.Status.PENDING:
            payment.status = PaymentTransaction.Status.CANCELLED
            payment.save(update_fields=["status", "updated_at"])
        AuditLog.objects.create(
            actor=request.user,
            action=f"admin_booking_{action}",
            entity_type="booking",
            entity_id=booking.id,
            metadata={"customer_id": booking.customer_id, "vehicle_id": booking.vehicle_id},
        )
    return JsonResponse({"ok": True, "message": f"Booking marked {status_by_action[action].lower()}."})
