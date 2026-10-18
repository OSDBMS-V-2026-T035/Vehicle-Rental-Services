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
        "id": payment.id, "booking_id": payment.booking_id,
        "amount": str(payment.amount),
        "customer": payment.customer.get_full_name() or payment.customer.email,
        "vehicle": payment.booking.vehicle.display_name,
        "shop": payment.booking.vehicle.shopkeeper.shop_name,
        "created_at": payment.created_at.isoformat(),
    } for payment in payments]})


@_admin_only
@require_GET
def admin_catalog(request, resource):
    """Dedicated, paged workspace data for each admin operation area."""
    if resource == "shopkeepers":
        rows = ShopkeeperProfile.objects.select_related("user").annotate(vehicle_count=Count("vehicles"))[:200]
        return JsonResponse({"ok": True, "rows": [{
            "id": row.id, "name": row.shop_name, "address": row.shop_address,
            "email": row.user.email, "phone": row.user.phone_number,
            "description": row.shop_description, "latitude": str(row.latitude or ""), "longitude": str(row.longitude or ""),
            "current_location": f"{row.latitude}, {row.longitude}" if row.latitude is not None and row.longitude is not None else "Not added",
            "legal_business_name": row.legal_business_name, "proprietor_name": row.proprietor_name,
            "business_type": row.business_type, "gstin": row.gstin, "pan_number": row.pan_number,
            "aadhaar_last4": row.aadhaar_last4, "business_registration_number": row.business_registration_number,
            "compliance_complete": row.is_compliance_complete,
            "shop_photo_url": row.shop_photo.url if row.shop_photo else "",
            "address_proof_url": row.address_proof.url if row.address_proof else "",
            "pan_document_url": row.pan_document.url if row.pan_document else "",
            "aadhaar_document_url": row.aadhaar_document.url if row.aadhaar_document else "",
            "gst_certificate_url": row.gst_certificate.url if row.gst_certificate else "",
            "status": row.verification_status, "vehicle_count": row.vehicle_count,
            "active": row.user.is_active, "action_url": f"/api/admin/shopkeepers/{row.id}/action/",
        } for row in rows]})
    if resource == "vehicles":
        rows = Vehicle.objects.select_related("shopkeeper", "shopkeeper__user")[:200]
        return JsonResponse({"ok": True, "rows": [{
            "id": row.id, "name": row.display_name, "registration_number": row.registration_number,
            "shop": row.shopkeeper.shop_name, "rate": str(row.daily_rate), "quantity": row.quantity,
            "available": row.is_available, "status": row.listing_status, "type": row.get_vehicle_type_display(),
            "brand": row.brand, "model": row.model_name, "year": row.manufacturing_year,
            "fuel": row.fuel_type, "seats": row.seating_capacity, "description": row.description,
            "image_url": row.image.url if row.image else "",
            "rc_number": row.rc_number, "insurance_policy_number": row.insurance_policy_number,
            "insurance_expiry_date": row.insurance_expiry_date.isoformat() if row.insurance_expiry_date else "",
            "rc_document_url": row.rc_document.url if row.rc_document else "",
            "insurance_document_url": row.insurance_document.url if row.insurance_document else "",
            "vehicle_photos": [photo.url for photo in (row.vehicle_photo_front, row.vehicle_photo_rear, row.vehicle_photo_left, row.vehicle_photo_right) if photo],
            "action_url": f"/api/admin/vehicles/{row.id}/action/",
        } for row in rows]})
    if resource == "bookings":
        rows = Booking.objects.select_related("customer", "vehicle", "vehicle__shopkeeper", "payment")[:200]
        return JsonResponse({"ok": True, "rows": [{
            "id": row.id, "customer": row.customer.get_full_name() or row.customer.email,
            "vehicle": row.vehicle.display_name, "shop": row.vehicle.shopkeeper.shop_name,
            "pickup": row.pickup_date.isoformat(), "return_date": row.return_date.isoformat(),
            "amount": str(row.total_amount), "status": row.status,
            "payment_status": row.payment.status if hasattr(row, "payment") else "PENDING",
            "renter_email": row.renter_email or row.customer.email,
            "renter_phone": row.renter_phone or row.customer.phone_number,
            "action_url": f"/api/admin/bookings/{row.id}/action/",
        } for row in rows]})
    if resource == "customers":
        rows = User.objects.filter(role=User.Role.USER).order_by("-created_at")[:200]
        return JsonResponse({"ok": True, "rows": [{
            "id": row.id, "name": row.get_full_name() or row.email, "email": row.email,
            "phone": row.phone_number, "role": row.get_role_display(), "email_verified": row.is_email_verified,
            "active": row.is_active,
            "banned": row.is_permanently_banned, "action_url": f"/api/admin/users/{row.id}/action/",
        } for row in rows]})
    return JsonResponse({"ok": False, "message": "Unknown admin workspace."}, status=404)
