import logging
from html import escape

from apps.accounts.services import send_transactional_email
from .models import Notification

logger = logging.getLogger(__name__)


def notify_user(user, title, message, *, email=True):
    """Persist a user notice and mirror it to branded email when configured."""
    notice = Notification.objects.create(user=user, title=title, message=message)
    if email:
        try:
            body = f'<p style="font-size:16px;line-height:1.6">{message}</p>'
            notice.email_sent = send_transactional_email(user.email, title, title, message, body) != "console"
            notice.save(update_fields=["email_sent"])
        except Exception:
            logger.exception("Could not email notification to %s", user.email)
    return notice


def notify_signup_success(user):
    """Send a branded, non-sensitive account receipt after signup."""
    role = user.get_role_display()
    full_name = user.get_full_name().strip() or user.email
    details = (
        ("Full name", full_name),
        ("Email address", user.email),
        ("Mobile number", user.phone_number),
        ("Account type", role),
        ("Email status", "Verified" if user.is_email_verified else "Pending verification"),
    )
    rows = "".join(
        f'<tr><td style="padding:11px 0;color:#65758a;font-size:14px;border-bottom:1px solid #e7eef5;">{escape(label)}</td>'
        f'<td style="padding:11px 0;text-align:right;color:#102d4c;font-size:14px;font-weight:700;border-bottom:1px solid #e7eef5;">{escape(value)}</td></tr>'
        for label, value in details
    )
    title = "Your RideHub account is ready"
    message = f"Welcome, {full_name}. Your {role.lower()} account has been created successfully."
    body = (
        f'<p style="font-size:16px;line-height:1.6;margin:0 0 18px;">Hello {escape(full_name)},</p>'
        f'<p style="font-size:16px;line-height:1.6;margin:0 0 22px;">Your RideHub {escape(role.lower())} account has been created successfully. Here is your account summary:</p>'
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;margin:0 0 20px;">{rows}</table>'
        '<p style="font-size:13px;line-height:1.6;color:#65758a;margin:0;">For your security, we never include passwords, OTPs, or payment details in account notifications.</p>'
    )
    notice = Notification.objects.create(user=user, title=title, message=message)
    try:
        notice.email_sent = send_transactional_email(
            user.email,
            "Welcome to RideHub — account created successfully",
            title,
            "Your RideHub account is ready. Review your account details inside.",
            body,
        ) != "console"
        notice.save(update_fields=["email_sent"])
    except Exception:
        logger.exception("Could not email signup confirmation to %s", user.email)
    return notice
