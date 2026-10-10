"""OTP and branded transactional email delivery."""
import json
import logging
import secrets
from datetime import timedelta
from email.utils import parseaddr
from html import escape
from urllib import request as urlrequest

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone

from .models import OTPChallenge

logger = logging.getLogger(__name__)


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


def normalize_contact(channel, contact):
    return contact.strip().lower() if channel == OTPChallenge.Channel.EMAIL else "".join(char for char in contact if char.isdigit())


def generate_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def _template(title, preheader, body):
    """Email-client-safe shell based on the shared KFC messaging pattern."""
    company = escape(getattr(settings, "EMAIL_BRAND_NAME", "RideHub"))
    heading = escape(title or "RideHub update")
    preview = escape(preheader or heading)
    logo_url = getattr(settings, "EMAIL_BRAND_LOGO_URL", "").strip()
    if logo_url:
        logo = f'<img src="{escape(logo_url, quote=True)}" width="44" height="44" alt="{company}" style="display:block;width:44px;height:44px;max-width:44px;border-radius:12px;object-fit:contain;background:#ffffff;" />'
    else:
        logo = '<div style="width:44px;height:44px;border-radius:12px;background:#e4002b;color:#ffffff;font:800 25px/44px Arial,sans-serif;text-align:center;">R</div>'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#eef4f9;color:#16283d;font-family:Arial,Helvetica,sans-serif;"><div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{preview}</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#eef4f9;margin:0;padding:28px 12px;"><tr><td align="center"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:640px;background:#ffffff;border-radius:18px;overflow:hidden;box-shadow:0 14px 38px rgba(23,45,70,.13);">
<tr><td style="padding:26px 30px;background:#0b4f8c;"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr><td width="56" valign="middle">{logo}</td><td valign="middle" style="padding-left:12px;color:#ffffff;"><div style="font-size:18px;font-weight:700;letter-spacing:.2px;">{company}</div><div style="font-size:11px;letter-spacing:1.4px;text-transform:uppercase;color:#c4e4ff;margin-top:5px;">Official account update</div></td></tr></table></td></tr>
<tr><td style="padding:32px 30px 26px;"><div style="font-size:21px;line-height:1.32;font-weight:700;color:#102d4c;margin:0 0 18px;">{heading}</div>{body}</td></tr>
<tr><td style="padding:18px 30px;background:#f6f9fc;border-top:1px solid #e1eaf2;color:#718197;font-size:11px;line-height:1.55;">This is an automated message from {company}. Please do not share passwords, OTPs, or secure links with anyone.<br/>For assistance, reply to this email or contact RideHub support.</td></tr>
</table></td></tr></table></body></html>'''
def send_transactional_email(recipient, subject, title, preheader, body):
    """Use Brevo's API when configured, otherwise the configured SMTP backend."""
    api_key = getattr(settings, "BREVO_API_KEY", "")
    default_name, default_email = parseaddr(getattr(settings, "DEFAULT_FROM_EMAIL", ""))
    sender_email = getattr(settings, "BREVO_SENDER_EMAIL", "") or default_email
    sender_name = getattr(settings, "BREVO_SENDER_NAME", "") or default_name or "RideHub"
    html = _template(title, preheader, body)
    if api_key and sender_email:
        payload = json.dumps({"sender": {"email": sender_email, "name": sender_name or "RideHub"}, "to": [{"email": recipient}], "subject": subject, "htmlContent": html, "textContent": f"{title}\n\n{preheader}"}).encode("utf-8")
        req = urlrequest.Request("https://api.brevo.com/v3/smtp/email", data=payload, headers={"accept": "application/json", "api-key": api_key, "content-type": "application/json"}, method="POST")
        with urlrequest.urlopen(req, timeout=10):
            return "brevo"
    if getattr(settings, "EMAIL_HOST_USER", ""):
        message = EmailMultiAlternatives(subject, preheader, settings.DEFAULT_FROM_EMAIL, [recipient])
        message.attach_alternative(html, "text/html")
        message.send(fail_silently=False)
        return "smtp"
    return "console"


def send_otp(contact, channel, purpose, request):
    now = timezone.now()
    recent = OTPChallenge.objects.filter(contact=contact, channel=channel, purpose=purpose, created_at__gte=now - timedelta(hours=1))
    if recent.count() >= 5:
        raise ValueError("Too many OTP requests. Please try again later.")
    if recent.filter(created_at__gte=now - timedelta(seconds=60)).exists():
        raise ValueError("Please wait a minute before requesting another OTP.")
    code = generate_code()
    challenge = OTPChallenge.objects.create(contact=contact, channel=channel, purpose=purpose, code_hash=make_password(code), expires_at=now + timedelta(minutes=10), request_ip=client_ip(request))
    provider = "console"
    try:
        action = "reset your password" if purpose == OTPChallenge.Purpose.RESET else "verify your email"
        body = f'<p style="font-size:16px;line-height:1.6">Use this one-time code to {action}:</p><p style="font-size:32px;letter-spacing:8px;font-weight:800;color:#e4002b">{code}</p><p style="color:#6b7280">This code expires in 10 minutes and can only be used once.</p>'
        provider = send_transactional_email(contact, f"Your RideHub security code: {code}", "Your secure verification code", f"Your RideHub code is {code}. It expires in 10 minutes.", body)
    except Exception:
        logger.exception("OTP provider failed; retaining development fallback.")
    logger.info("RideHub %s OTP requested for %s (provider=%s)", channel, contact, provider)
    return challenge, provider, code


def verify_otp(contact, channel, purpose, code):
    challenge = OTPChallenge.objects.filter(contact=contact, channel=channel, purpose=purpose, verified_at__isnull=True).first()
    if not challenge or challenge.is_expired:
        return False
    if challenge.attempts >= 5 or not check_password(code, challenge.code_hash):
        challenge.attempts += 1
        challenge.save(update_fields=["attempts"])
        return False
    challenge.verified_at = timezone.now()
    challenge.save(update_fields=["verified_at"])
    return True




