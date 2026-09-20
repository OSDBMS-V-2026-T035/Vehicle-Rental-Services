import json
import re

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import OTPChallenge, ShopkeeperProfile, User, phone_validator
from .services import normalize_contact, send_otp, verify_otp


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


@ensure_csrf_cookie
def auth_page(request):
    return render(request, "auth.html")


@require_POST
def send_otp_view(request):
    payload = _payload(request)
    channel = str(payload.get("channel", "")).upper()
    if channel not in {OTPChallenge.Channel.EMAIL, OTPChallenge.Channel.SMS}:
        return _error("Choose a valid OTP channel.")
    try:
        contact = _clean_email(payload.get("contact")) if channel == OTPChallenge.Channel.EMAIL else _clean_phone(payload.get("contact"))
        _, provider, code = send_otp(contact, channel, OTPChallenge.Purpose.SIGNUP, request)
    except (ValidationError, ValueError) as exc:
        return _error(exc.messages[0] if hasattr(exc, "messages") else str(exc))
    response = {"ok": True, "message": f"Verification code sent through {provider}.", "provider": provider}
    if settings.DEBUG:
        response["debug_code"] = code
        response["message"] += " Development mode shows the code below."
    return JsonResponse(response)


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
        if role == User.Role.SHOPKEEPER and (len(shop_name) < 2 or len(shop_address) < 8):
            return _error("Shopkeeper signup needs a valid shop name and address.")
        if User.objects.filter(email=email).exists():
            return _error("An account with this email already exists.", field="email", status=409)
        if User.objects.filter(phone_number=phone).exists():
            return _error("An account with this phone number already exists.", field="phone", status=409)
        if not verify_otp(email, OTPChallenge.Channel.EMAIL, OTPChallenge.Purpose.SIGNUP, str(payload.get("email_otp") or "")):
            return _error("Email OTP is missing, incorrect, or expired.", field="email_otp")
        if not verify_otp(phone, OTPChallenge.Channel.SMS, OTPChallenge.Purpose.SIGNUP, str(payload.get("phone_otp") or "")):
            return _error("Mobile OTP is missing, incorrect, or expired.", field="phone_otp")

        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                phone_number=phone,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role,
                is_email_verified=True,
                is_phone_verified=True,
            )
            if role == User.Role.SHOPKEEPER:
                ShopkeeperProfile.objects.create(user=user, shop_name=shop_name, shop_address=shop_address)
    except (ValidationError, IntegrityError) as exc:
        if isinstance(exc, IntegrityError):
            return _error("That email or phone number is already registered.", status=409)
        return _error(exc.messages[0])

    login(request, user, backend="apps.accounts.backends.EmailOrPhoneBackend")
    return JsonResponse({"ok": True, "message": "Account created successfully. Welcome to RideHub!", "redirect": "/"})


@require_POST
def login_view(request):
    payload = _payload(request)
    identifier = str(payload.get("identifier") or "").strip()
    password = str(payload.get("password") or "")
    requested_role = str(payload.get("role", User.Role.USER)).upper()
    if not identifier or not password:
        return _error("Enter your email/phone and password.")
    user = authenticate(request, username=identifier, password=password)
    if not user or user.role != requested_role:
        return _error("The role, login details, or password is incorrect.", status=401)
    if not user.is_email_verified or not user.is_phone_verified:
        return _error("Verify both your email and phone before logging in.", status=403)
    login(request, user, backend="apps.accounts.backends.EmailOrPhoneBackend")
    redirect = "/admin/" if user.role == User.Role.ADMIN else "/"
    return JsonResponse({"ok": True, "message": "Login successful. Welcome back!", "redirect": redirect})


@require_POST
def logout_view(request):
    logout(request)
    return JsonResponse({"ok": True, "message": "You have been logged out."})
