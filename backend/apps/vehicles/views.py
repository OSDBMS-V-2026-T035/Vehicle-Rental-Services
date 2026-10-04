import math
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import ShopkeeperProfile, User
from .models import Vehicle


def _distance_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    value = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return radius * 2 * math.asin(math.sqrt(value))


def _vehicle_payload(vehicle, distance=None):
    profile = vehicle.shopkeeper
    default_images = {
        "car": "/static/images/car.jpg",
        "bike": "/static/images/motorcycle.jpg",
        "scooter": "/static/images/scooter.jpg",
        "cycle": "/static/images/bicycle.jpg",
        "commercial": "/static/images/van.jpg",
    }
    result = {
        "id": vehicle.id,
        "name": vehicle.display_name,
        "type": vehicle.vehicle_type,
        "brand": vehicle.brand,
        "model": vehicle.model_name,
        "registration_number": vehicle.registration_number,
        "daily_rate": str(vehicle.daily_rate),
        "seating_capacity": vehicle.seating_capacity,
        "description": vehicle.description,
        "shop": profile.shop_name,
        "address": profile.shop_address,
        "image_url": vehicle.image.url if vehicle.image else default_images.get(vehicle.vehicle_type, "/static/images/car.jpg"),
    }
    if profile.latitude is not None and profile.longitude is not None:
        result["shop_latitude"] = float(profile.latitude)
        result["shop_longitude"] = float(profile.longitude)
        result["directions_url"] = (
            "https://www.google.com/maps/dir/?api=1&destination="
            f"{profile.latitude},{profile.longitude}"
        )
    if distance is not None:
        result["distance_km"] = round(distance, 1)
    return result


def _date_error(request):
    from django.utils.dateparse import parse_date

    pickup = parse_date(request.GET.get("pickup_date", "")) if request.GET.get("pickup_date") else None
    return_date = parse_date(request.GET.get("return_date", "")) if request.GET.get("return_date") else None
    if pickup and pickup < timezone.localdate():
        return "Pickup date cannot be in the past."
    if return_date:
        if return_date < (pickup or timezone.localdate()):
            return "Return date must be on or after pickup date."
        if pickup and return_date > pickup + timedelta(days=7):
            return "Return date cannot be more than 7 days after pickup."
    return None


@login_required
@require_POST
def create_vehicle(request):
    if request.user.role != User.Role.SHOPKEEPER:
        return JsonResponse({"ok": False, "message": "Only shopkeepers can submit vehicles."}, status=403)
    profile = getattr(request.user, "shopkeeper_profile", None)
    if not profile or profile.verification_status != ShopkeeperProfile.VerificationStatus.VERIFIED:
        return JsonResponse({"ok": False, "message": "Admin verification is required before listing vehicles."}, status=403)
    try:
        vehicle = Vehicle(
            shopkeeper=profile,
            vehicle_type=request.POST.get("vehicle_type", "").strip().lower(),
            brand=request.POST.get("brand", "").strip(),
            model_name=request.POST.get("model_name", "").strip(),
            registration_number=request.POST.get("registration_number", "").strip().upper(),
            manufacturing_year=int(request.POST.get("manufacturing_year", "0")),
            daily_rate=Decimal(request.POST.get("daily_rate", "0")),
            seating_capacity=int(request.POST.get("seating_capacity", "2")),
            description=request.POST.get("description", "").strip(),
            image=request.FILES.get("image"),
        )
        if vehicle.image:
            if not vehicle.image.content_type.startswith("image/"):
                raise ValidationError("Vehicle photo must be an image file.")
            if vehicle.image.size > 5 * 1024 * 1024:
                raise ValidationError("Vehicle photo must be 5 MB or smaller.")
        vehicle.full_clean()
        vehicle.save()
    except (ValueError, InvalidOperation, ValidationError) as exc:
        if hasattr(exc, "message_dict"):
            message = "; ".join(str(value[0]) for value in exc.message_dict.values())
        else:
            message = str(exc)
        return JsonResponse({"ok": False, "message": message}, status=400)
    return JsonResponse({"ok": True, "message": "Vehicle submitted for admin approval.", "id": vehicle.id})


@login_required
@require_GET
def my_vehicles(request):
    if request.user.role != User.Role.SHOPKEEPER:
        return JsonResponse({"ok": False, "message": "Shopkeeper access only."}, status=403)
    profile = getattr(request.user, "shopkeeper_profile", None)
    vehicles = profile.vehicles.all() if profile else Vehicle.objects.none()
    return JsonResponse({"ok": True, "vehicles": [_vehicle_payload(vehicle) for vehicle in vehicles]})


@require_GET
def search_vehicles(request):
    date_error = _date_error(request)
    if date_error:
        return JsonResponse({"ok": False, "message": date_error}, status=400)
    vehicle_type = request.GET.get("vehicle_type", "all").lower()
    query = request.GET.get("q", "").strip().lower()
    try:
        latitude = float(request.GET.get("latitude", ""))
        longitude = float(request.GET.get("longitude", ""))
    except ValueError:
        latitude = longitude = None
    vehicles = Vehicle.objects.filter(
        listing_status=Vehicle.ListingStatus.APPROVED,
        is_available=True,
        shopkeeper__verification_status=ShopkeeperProfile.VerificationStatus.VERIFIED,
        shopkeeper__user__is_active=True,
    ).select_related("shopkeeper")
    if vehicle_type != "all":
        vehicles = vehicles.filter(vehicle_type=vehicle_type)
    matches = []
    for vehicle in vehicles:
        searchable = f"{vehicle.brand} {vehicle.model_name} {vehicle.shopkeeper.shop_name} {vehicle.shopkeeper.shop_address}".lower()
        if query and query not in searchable:
            continue
        distance = None
        if latitude is not None and longitude is not None:
            if vehicle.shopkeeper.latitude is None or vehicle.shopkeeper.longitude is None:
                continue
            distance = _distance_km(latitude, longitude, float(vehicle.shopkeeper.latitude), float(vehicle.shopkeeper.longitude))
            try:
                radius = min(max(float(request.GET.get("radius", "25")), 1), 500)
            except ValueError:
                radius = 25
            if distance > radius:
                continue
        matches.append(_vehicle_payload(vehicle, distance))
    matches.sort(key=lambda item: item.get("distance_km", 0))
    return JsonResponse({"ok": True, "count": len(matches), "vehicles": matches[:100]})
