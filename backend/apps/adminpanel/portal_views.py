"""Read APIs for the protected administrator portal."""

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from apps.accounts.models import ShopkeeperProfile, User
from apps.bookings.models import Booking
from apps.payments.models import PaymentTransaction
from apps.vehicles.models import Vehicle
from .models import AuditLog


def _admin_only(view):
    @login_required
    def wrapped(request, *args, **kwargs):
        if request.user.role != User.Role.ADMIN or not request.user.is_staff:
            return JsonResponse({"ok": False, "message": "Administrator access only."}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


@_admin_only
@require_GET
def admin_summary(request):
    return JsonResponse({"ok": True, "summary": {
        "customers": User.objects.filter(role=User.Role.USER).count(),
        "pending_shops": ShopkeeperProfile.objects.filter(verification_status=ShopkeeperProfile.VerificationStatus.PENDING).count(),
        "pending_vehicles": Vehicle.objects.filter(listing_status=Vehicle.ListingStatus.PENDING).count(),
        "active_bookings": Booking.objects.filter(status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED]).count(),
        "paid_transactions": PaymentTransaction.objects.filter(status=PaymentTransaction.Status.PAID).count(),
        "gross_earnings": PaymentTransaction.objects.filter(status=PaymentTransaction.Status.PAID).aggregate(total=Sum("amount"))["total"] or 0,
        "open_audit_events": AuditLog.objects.count(),
    }})


@_admin_only
@require_GET
def admin_review_queues(request):
    shops = ShopkeeperProfile.objects.filter(verification_status=ShopkeeperProfile.VerificationStatus.PENDING).select_related("user").annotate(vehicle_count=Count("vehicles"))[:100]
    vehicles = Vehicle.objects.filter(listing_status=Vehicle.ListingStatus.PENDING).select_related("shopkeeper", "shopkeeper__user")[:100]
    users = User.objects.filter(role__in=[User.Role.USER, User.Role.SHOPKEEPER]).select_related("shopkeeper_profile").order_by("-created_at")[:100]
    accounts = []
    for item in users:
        is_shopkeeper = item.role == User.Role.SHOPKEEPER
        profile = getattr(item, "shopkeeper_profile", None)
        accounts.append({"id": item.id, "name": item.get_full_name() or item.email, "email": item.email, "phone": item.phone_number, "role": item.get_role_display(), "active": item.is_active, "permanently_banned": item.is_permanently_banned, "action_url": f"/api/admin/shopkeepers/{profile.id}/action/" if is_shopkeeper and profile else f"/api/admin/users/{item.id}/action/", "created_at": item.created_at.isoformat()})
    return JsonResponse({"ok": True, "shopkeepers": [{"id": item.id, "shop_name": item.shop_name, "address": item.shop_address, "email": item.user.email, "phone": item.user.phone_number, "vehicle_count": item.vehicle_count, "created_at": item.created_at.isoformat()} for item in shops], "vehicles": [{"id": item.id, "name": item.display_name, "registration_number": item.registration_number, "shop": item.shopkeeper.shop_name, "daily_rate": str(item.daily_rate), "created_at": item.created_at.isoformat()} for item in vehicles], "users": accounts})


@_admin_only
@require_GET
def admin_audit(request):
    events = AuditLog.objects.select_related("actor")[:100]
    return JsonResponse({"ok": True, "events": [{"id": event.id, "action": event.action, "entity_type": event.entity_type, "entity_id": event.entity_id, "actor": event.actor.email if event.actor else "System", "created_at": event.created_at.isoformat()} for event in events]})


@_admin_only
@require_GET
def admin_earnings(request):
    payments = PaymentTransaction.objects.filter(status=PaymentTransaction.Status.PAID).select_related(
        "booking", "booking__vehicle", "booking__vehicle__shopkeeper", "customer"
    )[:100]
    total = PaymentTransaction.objects.filter(status=PaymentTransaction.Status.PAID).aggregate(total=Sum("amount"))["total"] or 0
    return JsonResponse({"ok": True, "total": str(total), "count": PaymentTransaction.objects.filter(status=PaymentTransaction.Status.PAID).count(), "payments": [{
        "id": payment.id,
        "amount": str(payment.amount),
        "customer": payment.customer.get_full_name() or payment.customer.email,
        "vehicle": payment.booking.vehicle.display_name,
        "shop": payment.booking.vehicle.shopkeeper.shop_name,
        "created_at": payment.created_at.isoformat(),
    } for payment in payments]})
