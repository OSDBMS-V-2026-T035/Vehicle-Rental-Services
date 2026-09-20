"""OTP delivery adapters using Django and the Python standard library only."""

import base64
import json
import logging
import secrets
from datetime import timedelta
from email.utils import parseaddr
from urllib import parse, request as urlrequest

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import OTPChallenge

logger = logging.getLogger(__name__)


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


def normalize_contact(channel, contact):
    if channel == OTPChallenge.Channel.EMAIL:
        return contact.strip().lower()
    return "".join(character for character in contact if character.isdigit())


def generate_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def _send_brevo_email(recipient, code):
    api_key = getattr(settings, "BREVO_API_KEY", "")
    sender = getattr(settings, "DEFAULT_FROM_EMAIL", "")
    sender_name, sender_email = parseaddr(sender)
    if not api_key or not sender_email:
        return False
    payload = json.dumps(
        {
            "sender": {"email": sender_email, "name": sender_name or "RideHub"},
            "to": [{"email": recipient}],
            "subject": "Your RideHub verification code",
            "textContent": f"Your RideHub verification code is {code}. It expires in 10 minutes.",
        }
    ).encode("utf-8")
    req = urlrequest.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=payload,
        headers={"accept": "application/json", "api-key": api_key, "content-type": "application/json"},
        method="POST",
    )
    with urlrequest.urlopen(req, timeout=10):
        return True


def _send_twilio_sms(phone_number):
    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
    service_sid = getattr(settings, "TWILIO_VERIFY_SERVICE_SID", "")
    if not all((account_sid, auth_token, service_sid)):
        return False
    payload = parse.urlencode({"To": f"+91{phone_number}", "Channel": "sms"}).encode("utf-8")
    credentials = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
    req = urlrequest.Request(
        f"https://verify.twilio.com/v2/Services/{service_sid}/Verifications",
        data=payload,
        headers={"Authorization": f"Basic {credentials}"},
        method="POST",
    )
    with urlrequest.urlopen(req, timeout=10):
        return True


def send_otp(contact, channel, purpose, request):
    """Create an OTP, rate-limit sends, and deliver through an optional provider."""
    now = timezone.now()
    recent = OTPChallenge.objects.filter(
        contact=contact,
        channel=channel,
        purpose=purpose,
        created_at__gte=now - timedelta(hours=1),
    )
    if recent.count() >= 5:
        raise ValueError("Too many OTP requests. Please try again later.")
    if recent.filter(created_at__gte=now - timedelta(seconds=60)).exists():
        raise ValueError("Please wait a minute before requesting another OTP.")

    code = generate_code()
    with transaction.atomic():
        challenge = OTPChallenge.objects.create(
            contact=contact,
            channel=channel,
            purpose=purpose,
            code_hash=make_password(code),
            expires_at=now + timedelta(minutes=10),
            request_ip=client_ip(request),
        )

    provider = "console"
    try:
        if channel == OTPChallenge.Channel.EMAIL:
            if _send_brevo_email(contact, code):
                provider = "brevo"
            elif getattr(settings, "EMAIL_HOST_USER", ""):
                send_mail(
                    "Your RideHub verification code",
                    f"Your RideHub verification code is {code}. It expires in 10 minutes.",
                    settings.DEFAULT_FROM_EMAIL,
                    [contact],
                    fail_silently=False,
                )
                provider = "smtp"
        elif channel == OTPChallenge.Channel.SMS and _send_twilio_sms(contact):
            provider = "twilio"
    except Exception:
        logger.exception("OTP provider failed; keeping the challenge for local development.")
        provider = "console"

    logger.info("RideHub %s OTP for %s: %s (provider=%s)", channel, contact, code, provider)
    return challenge, provider, code


def verify_otp(contact, channel, purpose, code):
    challenge = OTPChallenge.objects.filter(
        contact=contact,
        channel=channel,
        purpose=purpose,
        verified_at__isnull=True,
    ).first()
    if not challenge or challenge.is_expired:
        return False
    if challenge.attempts >= 5 or not check_password(code, challenge.code_hash):
        challenge.attempts += 1
        challenge.save(update_fields=["attempts"])
        return False
    challenge.verified_at = timezone.now()
    challenge.save(update_fields=["verified_at"])
    return True
