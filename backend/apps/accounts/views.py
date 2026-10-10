import json
import re
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import OTPChallenge, ShopkeeperProfile, User, phone_validator
from .captcha import create_captcha, verify_captcha
from .services import normalize_contact, send_otp, verify_otp
from apps.notifications.services import notify_signup_success, notify_user

def _captcha_error(payload):
    return None if verify_captcha(payload.get("captcha_id"), payload.get("captcha_answer")) else _error("Invalid or expired security code. Please try the new code.", field="captcha_answer")


def _payload(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}


def _error(message, status=400, field=None):
    payload = {"ok": False, "message": message}
    if field:
        payload["field"] = field
    return JsonResponse(payload, status=status)


def _mask_email(email):
    local, _, domain = email.partition("@")
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}{'*' * max(3, len(local) - len(visible))}@{domain}"

def _clean_email(value):
    email = str(value or "").strip().lower()
    validate_email(email)
    return email


def _clean_phone(value):
    phone = normalize_contact(OTPChallenge.Channel.SMS, str(value or ""))
    phone_validator(phone)
    return phone


def _clean_name(value):
    name = " ".join(str(value or "").strip().split())
    if len(name) < 2 or not re.fullmatch(r"[A-Za-z][A-Za-z .'-]+", name):
        raise ValidationError("Enter a valid full name using letters and spaces only.")
    return name


def _clean_coordinate(value, minimum, maximum, field_name):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        coordinate = Decimal(raw)
    except InvalidOperation as exc:
        raise ValidationError(f"Enter a valid {field_name}.") from exc
    if coordinate < minimum or coordinate > maximum:
        raise ValidationError(f"Enter a valid {field_name}.")
    return coordinate


def portal_view(request, portal_role):
    """Render role-specific placeholders while the real portals are being built."""
    if not request.user.is_authenticated:
        return redirect("/auth/")

    portal_config = {
        "USER": (User.Role.USER, "User Portal", "Your RideHub customer space", "Your bookings, saved vehicles, and ride activity will appear here soon."),
        "SHOPKEEPER": (User.Role.SHOPKEEPER, "Shopkeeper Portal", "Your RideHub business space", "Vehicle management, bookings, and shop controls are under development."),
        "ADMIN": (User.Role.ADMIN, "Admin Portal", "Your RideHub operations space", "Platform moderation, account management, and reports are under development."),
    }
    expected_role, title, subtitle, description = portal_config[portal_role]
    if request.user.role != expected_role:
        return render(request, "access_denied.html", {"message": "You do not have access to this portal."}, status=403)

    return render(request, "portal_placeholder.html", {
        "portal_title": title,
        "portal_subtitle": subtitle,
        "portal_description": description,
        "user_name": request.user.get_full_name() or request.user.email,
        "role_label": request.user.get_role_display(),
    })

@ensure_csrf_cookie
def auth_page(request):
    return render(request, "auth.html")


@require_POST
def send_otp_view(request):
    payload = _payload(request)
    captcha_error = _captcha_error(payload)
    if captcha_error: return captcha_error
    channel = str(payload.get("channel", "")).upper()
    if channel != OTPChallenge.Channel.EMAIL:
        return _error("Only email OTP verification is available.")
    try:
        contact = _clean_email(payload.get("contact"))
        _, provider, _ = send_otp(contact, channel, OTPChallenge.Purpose.SIGNUP, request)
    except (ValidationError, ValueError) as exc:
        return _error(exc.messages[0] if hasattr(exc, "messages") else str(exc))
    return JsonResponse({"ok": True, "message": f"A verification code was sent to {_mask_email(contact)}. A new security code is now displayed below—enter it before creating your account.", "provider": provider})


@require_POST
def signup_view(request):
    payload = _payload(request)
    role = str(payload.get("role", User.Role.USER)).upper()
    if role not in {User.Role.USER, User.Role.SHOPKEEPER}:
        return _error("Administrator accounts are created only by the system owner.")

    try:
        full_name = _clean_name(payload.get("full_name"))
        email = _clean_email(payload.get("email"))
        phone = _clean_phone(payload.get("phone"))
        password = str(payload.get("password") or "")
        if password != str(payload.get("confirm_password") or ""):
            return _error("Passwords do not match.", field="confirm_password")
        if not payload.get("terms"):
            return _error("Accept the Terms and Privacy Policy to continue.", field="terms")
        first_name, *last_names = full_name.split(" ")
        last_name = " ".join(last_names)
        candidate = User(email=email, phone_number=phone, first_name=first_name, last_name=last_name, role=role)
        validate_password(password, candidate)
        shop_name = str(payload.get("shop_name") or "").strip()
        shop_address = str(payload.get("shop_address") or "").strip()
        shop_latitude = _clean_coordinate(payload.get("shop_latitude"), Decimal("-90"), Decimal("90"), "shop latitude")
        shop_longitude = _clean_coordinate(payload.get("shop_longitude"), Decimal("-180"), Decimal("180"), "shop longitude")
        shop_place_id = str(payload.get("shop_place_id") or "").strip()[:255]
        if (shop_latitude is None) != (shop_longitude is None):
            return _error("Shop latitude and longitude must be provided together.")
        if role == User.Role.SHOPKEEPER and (len(shop_name) < 2 or len(shop_address) < 8):
            return _error("Shopkeeper signup needs a valid shop name and address.")
        if User.objects.filter(email=email).exists():
            return _error("An account with this email already exists.", field="email", status=409)
        if User.objects.filter(phone_number=phone).exists():
            return _error("An account with this phone number already exists.", field="phone", status=409)
        captcha_error = _captcha_error(payload)
        if captcha_error: return captcha_error

        if not verify_otp(email, OTPChallenge.Channel.EMAIL, OTPChallenge.Purpose.SIGNUP, str(payload.get("email_otp") or "")):
            return _error("Email OTP is missing, incorrect, or expired.", field="email_otp")

        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                phone_number=phone,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role,
                is_email_verified=True,
                # Phone format is validated above; no mobile OTP provider is used.
                is_phone_verified=False,
            )
            if role == User.Role.SHOPKEEPER:
                ShopkeeperProfile.objects.create(
                    user=user,
                    shop_name=shop_name,
                    shop_address=shop_address,
                    latitude=shop_latitude,
                    longitude=shop_longitude,
                    google_place_id=shop_place_id,
                )
    except (ValidationError, IntegrityError) as exc:
        if isinstance(exc, IntegrityError):
            return _error("That email or phone number is already registered.", status=409)
        return _error(exc.messages[0])

    notify_signup_success(user)
    login(request, user, backend="apps.accounts.backends.EmailOrPhoneBackend")
    if role == User.Role.SHOPKEEPER:
        message = "Shopkeeper account created. You have temporary access while the admin reviews your shop."
        redirect = "/shopkeeper/"
    else:
        message = "Account created successfully. Welcome to RideHub!"
        redirect = "/user-portal/"
    return JsonResponse({"ok": True, "message": message, "redirect": redirect})


@require_POST
def password_reset_otp_view(request):
    payload = _payload(request)
    try:
        email = _clean_email(payload.get("email"))
    except ValidationError as exc:
        return _error(exc.messages[0], field="reset-email")
    if User.objects.filter(email=email, is_active=True).exists():
        try:
            _, provider, _ = send_otp(email, OTPChallenge.Channel.EMAIL, OTPChallenge.Purpose.RESET, request)
        except ValueError as exc:
            return _error(str(exc))
    else:
        provider, code = "console", None
    return JsonResponse({"ok": True, "message": "If an account exists, a reset code has been sent. A new security code is now displayed below—enter it before resetting your password.", "provider": provider})


@require_POST
def password_reset_confirm_view(request):
    payload = _payload(request)
    try:
        email = _clean_email(payload.get("email"))
        password = str(payload.get("password") or "")
        if password != str(payload.get("confirm_password") or ""):
            return _error("Passwords do not match.", field="reset-confirm-password")
        user = User.objects.get(email=email, is_active=True)
        validate_password(password, user)
    except User.DoesNotExist:
        return _error("The reset code or email is invalid.")
    except ValidationError as exc:
        return _error(exc.messages[0])
    captcha_error = _captcha_error(payload)
    if captcha_error: return captcha_error

    if not verify_otp(email, OTPChallenge.Channel.EMAIL, OTPChallenge.Purpose.RESET, str(payload.get("otp") or "")):
        return _error("The reset code is incorrect, expired, or already used.", field="reset-otp")
    user.set_password(password)
    user.save(update_fields=["password", "updated_at"])
    notify_user(user, "Password changed", "Your RideHub password was changed successfully. If this was not you, contact support immediately.")
    return JsonResponse({"ok": True, "message": "Password updated. You can now log in with your new password."})

@require_POST
def login_view(request):
    payload = _payload(request)
    identifier = str(payload.get("identifier") or "").strip()
    password = str(payload.get("password") or "")
    requested_role = str(payload.get("role", User.Role.USER)).upper()
    if not identifier or not password:
        return _error("Enter your email/phone and password.")
    captcha_error = _captcha_error(payload)
    if captcha_error: return captcha_error

    user = authenticate(request, username=identifier, password=password)
    if not user or user.role != requested_role:
        return _error("The role, login details, or password is incorrect.", status=401)
    if not user.is_email_verified:
        return _error("Verify your email before logging in.", status=403)
    if user.role == User.Role.SHOPKEEPER:
        profile = getattr(user, "shopkeeper_profile", None)
        if not profile:
            return _error("Shopkeeper profile is incomplete. Contact the administrator.", status=403)
        if profile.verification_status == ShopkeeperProfile.VerificationStatus.REVOKED or not user.is_active:
            return _error("This shopkeeper account has been revoked.", status=403)
    login(request, user, backend="apps.accounts.backends.EmailOrPhoneBackend")
    if user.role == User.Role.ADMIN:
        redirect = "/control-panel/"
        message = "Admin login successful."
    elif user.role == User.Role.SHOPKEEPER:
        redirect = "/shopkeeper/"
        if user.shopkeeper_profile.verification_status == ShopkeeperProfile.VerificationStatus.PENDING:
            message = "Login successful. Your shopkeeper request is pending admin verification."
        elif user.shopkeeper_profile.verification_status == ShopkeeperProfile.VerificationStatus.REJECTED:
            message = "Login successful. Update your shop profile and submit it for review again."
        else:
            message = "Login successful. Your shopkeeper workspace is ready."
    else:
        redirect = "/user-portal/"
        message = "Login successful. Welcome back!"
    return JsonResponse({"ok": True, "message": message, "redirect": redirect})


@require_POST
def logout_view(request):
    logout(request)
    return JsonResponse({"ok": True, "message": "You have been logged out."})




@require_POST
def captcha_view(request):
    return JsonResponse(create_captcha())









