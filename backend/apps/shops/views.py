import math
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import ShopkeeperProfile, User
from apps.vehicles.models import Vehicle


def _distance_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.asin(math.sqrt(value))


def _coordinates(request):
    try:
        latitude = float(request.GET.get("latitude", ""))
        longitude = float(request.GET.get("longitude", ""))
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError
        return latitude, longitude
    except (TypeError, ValueError):
        return None, None


def _shop_payload(profile, distance=None):
    result = {
        "id": profile.id,
        "name": profile.shop_name,
        "address": profile.shop_address,
        "latitude": float(profile.latitude) if profile.latitude is not None else None,
        "longitude": float(profile.longitude) if profile.longitude is not None else None,
        "vehicle_count": profile.vehicles.filter(
            listing_status=Vehicle.ListingStatus.APPROVED, is_available=True
        ).count(),
    }
    if distance is not None:
        result["distance_km"] = round(distance, 1)
    if result["latitude"] is not None and result["longitude"] is not None:
        result["directions_url"] = (
            "https://www.google.com/maps/dir/?api=1&destination="
            f"{result['latitude']},{result['longitude']}"
        )
    return result


@login_required
def shopkeeper_dashboard(request):
    if request.user.role != User.Role.SHOPKEEPER:
        return render(request, "access_denied.html", {"message": "Shopkeeper access only."}, status=403)
    profile = getattr(request.user, "shopkeeper_profile", None)
    if not profile:
        return render(request, "access_denied.html", {"message": "Shopkeeper profile is incomplete."}, status=403)
    vehicles = profile.vehicles.all()
    return render(request, "shopkeeper_dashboard.html", {"profile": profile, "vehicles": vehicles})


@login_required
@require_POST
def update_shopkeeper_profile(request):
    if request.user.role != User.Role.SHOPKEEPER:
        return JsonResponse({"ok": False, "message": "Shopkeeper access only."}, status=403)
    profile = getattr(request.user, "shopkeeper_profile", None)
    if not profile or profile.verification_status == ShopkeeperProfile.VerificationStatus.REVOKED:
        return JsonResponse({"ok": False, "message": "This shopkeeper account cannot be edited."}, status=403)
    name = " ".join(request.POST.get("shop_name", "").strip().split())
    address = " ".join(request.POST.get("shop_address", "").strip().split())
    if len(name) < 2 or len(address) < 8:
        return JsonResponse({"ok": False, "message": "Enter a valid shop name and complete address."}, status=400)
    try:
        latitude = Decimal(request.POST.get("latitude", "")) if request.POST.get("latitude") else None
        longitude = Decimal(request.POST.get("longitude", "")) if request.POST.get("longitude") else None
    except InvalidOperation:
        return JsonResponse({"ok": False, "message": "Enter valid map coordinates."}, status=400)
    if (latitude is None) != (longitude is None):
        return JsonResponse({"ok": False, "message": "Latitude and longitude must be provided together."}, status=400)
    if latitude is not None and not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return JsonResponse({"ok": False, "message": "Map coordinates are outside valid global limits."}, status=400)
    profile.shop_name = name
    profile.shop_address = address
    profile.latitude = latitude
    profile.longitude = longitude
    profile.google_place_id = request.POST.get("place_id", "").strip()[:255]
    if profile.verification_status == ShopkeeperProfile.VerificationStatus.REJECTED:
        profile.verification_status = ShopkeeperProfile.VerificationStatus.PENDING
    profile.save()
    return JsonResponse({"ok": True, "message": "Shop profile saved and sent for admin review."})


@require_GET
def search_shops(request):
    query = request.GET.get("q", "").strip().lower()
    latitude, longitude = _coordinates(request)
    try:
        radius = min(max(float(request.GET.get("radius", "25")), 1), 500)
    except ValueError:
        radius = 25
    profiles = ShopkeeperProfile.objects.filter(
        verification_status=ShopkeeperProfile.VerificationStatus.VERIFIED,
        user__is_active=True,
    ).prefetch_related("vehicles")
    matches = []
    for profile in profiles:
        if query and query not in f"{profile.shop_name} {profile.shop_address}".lower():
            continue
        distance = None
        if latitude is not None and longitude is not None:
            if profile.latitude is None or profile.longitude is None:
                continue
            distance = _distance_km(latitude, longitude, float(profile.latitude), float(profile.longitude))
            if distance > radius:
                continue
        matches.append(_shop_payload(profile, distance))
    matches.sort(key=lambda item: item.get("distance_km", 0))
    return JsonResponse({"ok": True, "count": len(matches), "shops": matches[:100]})
