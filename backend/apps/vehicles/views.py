import json
import math
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import ShopkeeperProfile, User
from apps.bookings.models import Booking
from apps.bookings.services import active_reservation_filter, expire_checkout_holds
from .validators import normalize_chassis_number, normalize_policy_number, normalize_registration
from django.db import transaction
from .models import Vehicle


def _payload(request):
    """Read JSON requests safely while retaining form-request compatibility."""
    if request.content_type and request.content_type.startswith("application/json"):
        try:
            return json.loads(request.body or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}
    return request.POST


def _validate_vehicle_image(upload):
    """Validate an uploaded vehicle image before it becomes a model FieldFile."""
    if not upload:
        return
    if not (upload.content_type or "").startswith("image/"):
        raise ValidationError("Vehicle photo must be an image file.")
    if upload.size > 5 * 1024 * 1024:
        raise ValidationError("Vehicle photo must be 5 MB or smaller.")


def _validate_document(upload, label):
    if not upload:
        raise ValidationError(f"Upload the {label}.")
    if upload.size > 8 * 1024 * 1024:
        raise ValidationError(f"{label} must be 8 MB or smaller.")
    content_type = upload.content_type or ""
    if content_type and not (content_type.startswith("image/") or content_type == "application/pdf"):
        raise ValidationError(f"{label} must be a PDF or image file.")


def _distance_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    value = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return radius * 2 * math.asin(math.sqrt(value))


def _vehicle_payload(vehicle, distance=None, reserved_units=None):
    profile = vehicle.shopkeeper
    default_images = {
        "car": "/static/images/car.jpg",
        "bike": "/static/images/motorcycle.jpg",
        "scooter": "/static/images/scooter.jpg",
        "cycle": "/static/images/bicycle.jpg",
        "commercial": "/static/images/van.jpg",
    }
    if reserved_units is None:
        available_units = vehicle.available_quantity
        availability_message = f"{available_units} of {vehicle.quantity} units available"
    else:
        available_units = max(0, vehicle.quantity - reserved_units)
        availability_message = (
            f"{available_units} of {vehicle.quantity} units available for these dates"
            if available_units
            else "Unavailable for these dates"
        )
    result = {
        "id": vehicle.id,
        "name": vehicle.display_name,
        "type": vehicle.vehicle_type,
        "brand": vehicle.brand,
        "model": vehicle.model_name,
        "registration_number": vehicle.registration_number,
        "daily_rate": str(vehicle.daily_rate),
        "seating_capacity": vehicle.seating_capacity,
        "body_style": vehicle.body_style,
        "fuel_type": vehicle.fuel_type,
        "fuel_capacity": str(vehicle.fuel_capacity or ""),
        "quantity": vehicle.quantity,
        "available_quantity": available_units,
        "reserved_units": reserved_units or 0,
        "availability_status": "AVAILABLE" if available_units > 0 else "UNAVAILABLE",
        "availability_message": availability_message,
        "description": vehicle.description,
        "listing_status": vehicle.listing_status,
        "is_available": vehicle.is_available,
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


def _search_filters(params):
    """Parse optional marketplace filters without silently accepting bad input."""
    result = {}
    raw_rate = str(params.get("max_daily_rate", "")).strip()
    if raw_rate:
        try:
            rate = Decimal(raw_rate)
        except (InvalidOperation, ValueError):
            return None, "Enter a valid maximum daily budget."
        if not rate.is_finite() or rate < 0 or rate > Decimal("100000000"):
            return None, "Maximum daily budget must be between ₹0 and ₹100,000,000."
        result["max_daily_rate"] = rate
    raw_seats = str(params.get("min_seats", "")).strip()
    if raw_seats:
        try:
            seats = int(raw_seats)
        except ValueError:
            return None, "Minimum seats must be a whole number."
        if not 1 <= seats <= 100:
            return None, "Minimum seats must be between 1 and 100."
        result["min_seats"] = seats
    fuel = str(params.get("fuel_type", "all")).strip().lower()
    if fuel not in {"all", "petrol", "diesel", "electric", "cng", "hybrid", "other"}:
        return None, "Choose a valid fuel type."
    if fuel != "all":
        result["fuel_type"] = fuel
    return result, None


@login_required
@require_POST
def create_vehicle(request):
    if request.user.role != User.Role.SHOPKEEPER:
        return JsonResponse({"ok": False, "message": "Only shopkeepers can submit vehicles."}, status=403)
    profile = getattr(request.user, "shopkeeper_profile", None)
    if not profile or profile.verification_status != ShopkeeperProfile.VerificationStatus.VERIFIED:
        return JsonResponse({"ok": False, "message": "Complete your compliance profile and obtain admin verification before submitting vehicles."}, status=403)
    if not profile.is_compliance_complete:
        return JsonResponse({"ok": False, "message": "Complete your shop compliance profile before submitting vehicles."}, status=409)
    if request.POST.get("vehicle_type", "").strip().lower() == "cycle":
        return JsonResponse({"ok": False, "message": "Bicycle listings are no longer supported."}, status=400)
    try:
        photos = {key: request.FILES.get(key) for key in ("vehicle_photo_front", "vehicle_photo_rear", "vehicle_photo_left", "vehicle_photo_right")}
        for label, upload in photos.items():
            if not upload:
                raise ValidationError("Upload clear front, rear, left and right vehicle photos.")
            _validate_vehicle_image(upload)
        rc_document = request.FILES.get("rc_document")
        insurance_document = request.FILES.get("insurance_document")
        _validate_document(rc_document, "RC document")
        _validate_document(insurance_document, "insurance document")
        uploaded_image = photos["vehicle_photo_front"]
        registration_number = normalize_registration(request.POST.get("registration_number"))
        rc_number = normalize_registration(request.POST.get("rc_number"), "RC registration number")
        if rc_number != registration_number:
            raise ValidationError("RC registration number must match the vehicle registration number above.")
        chassis_number = normalize_chassis_number(request.POST.get("chassis_number"))
        policy_number = normalize_policy_number(request.POST.get("insurance_policy_number"))
        if not rc_number or not policy_number or not request.POST.get("insurance_expiry_date"):
            raise ValidationError("Enter RC number, insurance policy number and insurance expiry date.")
        vehicle = Vehicle(
            shopkeeper=profile,
            vehicle_type=request.POST.get("vehicle_type", "").strip().lower(),
            brand=request.POST.get("brand", "").strip(),
            model_name=request.POST.get("model_name", "").strip(),
            registration_number=registration_number,
            manufacturing_year=int(request.POST.get("manufacturing_year", "0")),
            body_style=request.POST.get("body_style", "standard").strip().lower(),
            fuel_type=request.POST.get("fuel_type", "petrol").strip().lower(),
            fuel_capacity=Decimal(request.POST.get("fuel_capacity", "0") or "0") or None,
            daily_rate=Decimal(request.POST.get("daily_rate", "0")),
            seating_capacity=int(request.POST.get("seating_capacity", "2")),
            quantity=int(request.POST.get("quantity", "1")),
            available_quantity=int(request.POST.get("quantity", "1")),
            description=request.POST.get("description", "").strip(),
            image=uploaded_image,
            rc_number=rc_number,
            chassis_number=chassis_number,
            rc_document=rc_document,
            insurance_document=insurance_document,
            insurance_policy_number=policy_number,
            insurance_expiry_date=request.POST.get("insurance_expiry_date"),
            puc_document=request.FILES.get("puc_document"),
            puc_expiry_date=request.POST.get("puc_expiry_date") or None,
            vehicle_photo_front=photos["vehicle_photo_front"],
            vehicle_photo_rear=photos["vehicle_photo_rear"],
            vehicle_photo_left=photos["vehicle_photo_left"],
            vehicle_photo_right=photos["vehicle_photo_right"],
            listing_status=Vehicle.ListingStatus.PENDING,
            is_available=False,
            admin_note="Submitted for RideHub document review.",
        )
        vehicle.full_clean()
        vehicle.save()
    except (ValueError, InvalidOperation, ValidationError) as exc:
        if hasattr(exc, "message_dict"):
            message = "; ".join(str(value[0]) for value in exc.message_dict.values())
        else:
            message = str(exc)
        return JsonResponse({"ok": False, "message": message}, status=400)
    except IntegrityError:
        return JsonResponse({"ok": False, "message": "That registration number is already registered. Use a unique vehicle registration number."}, status=409)
    except DatabaseError:
        return JsonResponse({"ok": False, "message": "The vehicle database schema is not ready. Run the RideHub migration command and try again."}, status=503)
    return JsonResponse({"ok": True, "message": "Vehicle submitted successfully. The RideHub team will verify its documents before it becomes active.", "id": vehicle.id})


@login_required
@require_POST
def remove_vehicle(request, vehicle_id):
    """Archive a shopkeeper listing without destroying booking history."""
    if request.user.role != User.Role.SHOPKEEPER:
        return JsonResponse({"ok": False, "message": "Only shopkeepers can remove vehicles."}, status=403)
    profile = getattr(request.user, "shopkeeper_profile", None)
    if not profile:
        return JsonResponse({"ok": False, "message": "Shopkeeper profile not found."}, status=403)
    with transaction.atomic():
        try:
            vehicle = Vehicle.objects.select_for_update().get(pk=vehicle_id, shopkeeper=profile)
        except Vehicle.DoesNotExist:
            return JsonResponse({"ok": False, "message": "Vehicle not found in your fleet."}, status=404)
        if Booking.objects.filter(
            vehicle=vehicle,
            status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED],
            return_date__gte=timezone.localdate(),
        ).exists():
            return JsonResponse({"ok": False, "message": "Resolve current or upcoming bookings before removing this vehicle."}, status=409)
        vehicle.is_available = False
        vehicle.listing_status = Vehicle.ListingStatus.REJECTED
        vehicle.admin_note = "Removed from marketplace by shopkeeper."
        vehicle.save(update_fields=["is_available", "listing_status", "admin_note", "updated_at"])
    return JsonResponse({"ok": True, "message": "Vehicle removed from your active fleet."})


@login_required
@require_POST
def update_vehicle_inventory(request, vehicle_id):
    """Update an owned listing's fleet size without overbooking existing reservations."""
    if request.user.role != User.Role.SHOPKEEPER:
        return JsonResponse({"ok": False, "message": "Only shopkeepers can update fleet inventory."}, status=403)
    profile = getattr(request.user, "shopkeeper_profile", None)
    if not profile or profile.verification_status != ShopkeeperProfile.VerificationStatus.VERIFIED:
        return JsonResponse({"ok": False, "message": "Admin verification is required before changing inventory."}, status=403)
    try:
        quantity = int(_payload(request).get("quantity"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "message": "Enter a whole-number fleet quantity."}, status=400)
    if not 1 <= quantity <= 999:
        return JsonResponse({"ok": False, "message": "Fleet quantity must be between 1 and 999."}, status=400)
    with transaction.atomic():
        try:
            vehicle = Vehicle.objects.select_for_update().get(pk=vehicle_id, shopkeeper=profile)
        except Vehicle.DoesNotExist:
            return JsonResponse({"ok": False, "message": "Vehicle not found in your fleet."}, status=404)
        reserved = Booking.objects.filter(
            vehicle=vehicle,
            status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED],
            return_date__gte=timezone.localdate(),
        ).count()
        if quantity < reserved:
            return JsonResponse({"ok": False, "message": f"This listing has {reserved} active or upcoming reservation(s). Increase quantity or resolve them first."}, status=409)
        vehicle.quantity = quantity
        vehicle.available_quantity = max(0, quantity - reserved)
        vehicle.save(update_fields=["quantity", "available_quantity", "updated_at"])
    return JsonResponse({"ok": True, "message": "Fleet quantity updated successfully."})


@login_required
@require_GET
def my_vehicles(request):
    if request.user.role != User.Role.SHOPKEEPER:
        return JsonResponse({"ok": False, "message": "Shopkeeper access only."}, status=403)
    profile = getattr(request.user, "shopkeeper_profile", None)
    vehicles = profile.vehicles.all() if profile else Vehicle.objects.none()
    return JsonResponse({"ok": True, "vehicles": [_vehicle_payload(vehicle) for vehicle in vehicles]})


@require_GET
def vehicle_detail(request, vehicle_id):
    """Return the exact listing selected before authentication, with date-aware availability."""
    date_error = _date_error(request)
    if date_error:
        return JsonResponse({"ok": False, "message": date_error}, status=400)
    vehicle = Vehicle.objects.filter(
        pk=vehicle_id,
        listing_status=Vehicle.ListingStatus.APPROVED,
        is_available=True,
        quantity__gt=0,
        shopkeeper__verification_status=ShopkeeperProfile.VerificationStatus.VERIFIED,
        shopkeeper__user__is_active=True,
    ).select_related("shopkeeper").first()
    if vehicle is None:
        return JsonResponse({"ok": False, "message": "This vehicle is no longer available."}, status=404)
    from django.utils.dateparse import parse_date
    pickup = parse_date(request.GET.get("pickup_date", "")) if request.GET.get("pickup_date") else None
    return_date = parse_date(request.GET.get("return_date", "")) if request.GET.get("return_date") else None
    expire_checkout_holds()
    reserved = None
    if pickup and return_date:
        reserved = Booking.objects.filter(
            vehicle=vehicle,
            pickup_date__lte=return_date,
            return_date__gte=pickup,
        ).filter(active_reservation_filter()).count()
    return JsonResponse({"ok": True, "vehicle": _vehicle_payload(vehicle, reserved_units=reserved)})


@require_GET
def search_vehicles(request):
    date_error = _date_error(request)
    if date_error:
        return JsonResponse({"ok": False, "message": date_error}, status=400)
    expire_checkout_holds()
    vehicle_type = request.GET.get("vehicle_type", "all").lower()
    filters, filter_error = _search_filters(request.GET)
    if filter_error:
        return JsonResponse({"ok": False, "message": filter_error}, status=400)
    query = request.GET.get("q", "").strip().lower()
    shop_id = request.GET.get("shop_id", "").strip()
    try:
        latitude = float(request.GET.get("latitude", ""))
        longitude = float(request.GET.get("longitude", ""))
    except ValueError:
        latitude = longitude = None
    vehicles = Vehicle.objects.filter(
        listing_status=Vehicle.ListingStatus.APPROVED,
        is_available=True,
        quantity__gt=0,
        shopkeeper__verification_status=ShopkeeperProfile.VerificationStatus.VERIFIED,
        shopkeeper__user__is_active=True,
    ).exclude(vehicle_type=Vehicle.VehicleType.CYCLE).select_related("shopkeeper")
    from django.utils.dateparse import parse_date
    pickup = parse_date(request.GET.get("pickup_date", "")) if request.GET.get("pickup_date") else None
    return_date = parse_date(request.GET.get("return_date", "")) if request.GET.get("return_date") else None
    if vehicle_type != "all":
        if vehicle_type not in Vehicle.VehicleType.values:
            return JsonResponse({"ok": False, "message": "Choose a valid vehicle type."}, status=400)
        vehicles = vehicles.filter(vehicle_type=vehicle_type)
    if filters.get("max_daily_rate") is not None:
        vehicles = vehicles.filter(daily_rate__lte=filters["max_daily_rate"])
    if filters.get("min_seats") is not None:
        vehicles = vehicles.filter(seating_capacity__gte=filters["min_seats"])
    if filters.get("fuel_type"):
        vehicles = vehicles.filter(fuel_type__iexact=filters["fuel_type"])
    if shop_id:
        try:
            vehicles = vehicles.filter(shopkeeper_id=int(shop_id))
        except ValueError:
            return JsonResponse({"ok": False, "message": "That rental shop could not be identified."}, status=400)
    if pickup and return_date:
        # Keep unavailable listings in the response so the customer sees a
        # truthful "unavailable for these dates" card instead of a misleading
        # empty search result. The booking transaction repeats this check with
        # a row lock before creating a reservation.
        vehicles = vehicles.annotate(
            reserved_units=Count(
                "bookings",
                filter=Q(
                    bookings__pickup_date__lte=return_date,
                    bookings__return_date__gte=pickup,
                ) & active_reservation_filter(),
            )
        )
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
                radius = min(max(float(request.GET.get("radius", "15")), 1), 15)
            except ValueError:
                radius = 15
            if distance > radius:
                continue
        matches.append(_vehicle_payload(vehicle, distance, getattr(vehicle, "reserved_units", None)))
    matches.sort(key=lambda item: item.get("distance_km", 0))
    visible = matches[:100]
    return JsonResponse({
        "ok": True,
        "count": len(visible),
        "available_count": sum(item["availability_status"] == "AVAILABLE" for item in visible),
        "available_units_count": sum(item["available_quantity"] for item in visible),
        "vehicles": visible,
    })
