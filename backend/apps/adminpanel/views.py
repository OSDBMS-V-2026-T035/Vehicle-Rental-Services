import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.accounts.models import ShopkeeperProfile, User
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
    stats = {
        "pending_shops": pending_shops.count(),
        "pending_vehicles": pending_vehicles.count(),
        "users": User.objects.filter(role=User.Role.USER).count(),
        "verified_shops": ShopkeeperProfile.objects.filter(
            verification_status=ShopkeeperProfile.VerificationStatus.VERIFIED
        ).count(),
    }
    return render(request, "admin_dashboard.html", {
        "stats": stats,
        "pending_shops": pending_shops,
        "shopkeepers": shopkeepers,
        "pending_vehicles": pending_vehicles,
        "users": users,
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
    }
    if action not in status_by_action:
        return JsonResponse({"ok": False, "message": "Choose approve, reject, or revoke."}, status=400)
    with transaction.atomic():
        profile.verification_status = status_by_action[action]
        profile.user.is_active = action != "revoke"
        profile.user.save(update_fields=["is_active", "updated_at"])
        profile.save(update_fields=["verification_status", "updated_at"])
        AuditLog.objects.create(actor=request.user, action=f"shopkeeper_{action}", entity_type="shopkeeper", entity_id=profile.id, metadata={"email": profile.user.email})
    label = {"approve": "approved", "reject": "rejected", "revoke": "revoked"}[action]
    return JsonResponse({"ok": True, "message": f"Shopkeeper {label} successfully."})


@_admin_only
@require_POST
def vehicle_action(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
    action = _payload(request).get("action", "").lower()
    if action not in {"approve", "reject"}:
        return JsonResponse({"ok": False, "message": "Choose approve or reject."}, status=400)
    with transaction.atomic():
        vehicle.listing_status = Vehicle.ListingStatus.APPROVED if action == "approve" else Vehicle.ListingStatus.REJECTED
        vehicle.admin_note = str(_payload(request).get("note", "")).strip()[:255]
        vehicle.save(update_fields=["listing_status", "admin_note", "updated_at"])
        AuditLog.objects.create(actor=request.user, action=f"vehicle_{action}", entity_type="vehicle", entity_id=vehicle.id, metadata={"registration_number": vehicle.registration_number})
    return JsonResponse({"ok": True, "message": f"Vehicle {'approved' if action == 'approve' else 'rejected'} successfully."})


@_admin_only
@require_POST
def user_action(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if user == request.user:
        return JsonResponse({"ok": False, "message": "You cannot revoke your own admin account."}, status=400)
    action = _payload(request).get("action", "").lower()
    if action not in {"revoke", "restore"}:
        return JsonResponse({"ok": False, "message": "Choose revoke or restore."}, status=400)
    with transaction.atomic():
        user.is_active = action == "restore"
        user.save(update_fields=["is_active", "updated_at"])
        AuditLog.objects.create(actor=request.user, action=f"user_{action}", entity_type="user", entity_id=user.id, metadata={"email": user.email})
    return JsonResponse({"ok": True, "message": f"User {'restored' if action == 'restore' else 'revoked'} successfully."})
