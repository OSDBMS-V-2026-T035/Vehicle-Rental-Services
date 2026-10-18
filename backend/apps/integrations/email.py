"""Swappable delivery adapters for RideHub transactional email."""

import json
from base64 import b64encode
from email.utils import parseaddr
from urllib import request as urlrequest

from django.conf import settings
from django.core.mail import EmailMultiAlternatives


class BrevoEmailAdapter:
    name = "brevo"

    def send(self, recipient, subject, preheader, html, attachments):
        default_name, default_email = parseaddr(getattr(settings, "DEFAULT_FROM_EMAIL", ""))
        sender_email = getattr(settings, "BREVO_SENDER_EMAIL", "") or default_email
        sender_name = getattr(settings, "BREVO_SENDER_NAME", "") or default_name or "RideHub"
        payload_data = {
            "sender": {"email": sender_email, "name": sender_name},
            "to": [{"email": recipient}],
            "subject": subject,
            "htmlContent": html,
            "textContent": preheader,
        }
        if attachments:
            payload_data["attachment"] = [
                {"name": name, "content": b64encode(content).decode("ascii")}
                for name, content, _mime in attachments
            ]
        request = urlrequest.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=json.dumps(payload_data).encode("utf-8"),
            headers={"accept": "application/json", "api-key": settings.BREVO_API_KEY, "content-type": "application/json"},
            method="POST",
        )
        with urlrequest.urlopen(request, timeout=10):
            pass
        return self.name


class SmtpEmailAdapter:
    name = "smtp"

    def send(self, recipient, subject, preheader, html, attachments):
        message = EmailMultiAlternatives(subject, preheader, settings.DEFAULT_FROM_EMAIL, [recipient])
        message.attach_alternative(html, "text/html")
        for name, content, mime in attachments or ():
            message.attach(name, content, mime)
        message.send(fail_silently=False)
        return self.name


class ConsoleEmailAdapter:
    name = "console"

    def send(self, recipient, subject, preheader, html, attachments):
        return self.name


def get_transactional_email_adapter():
    """Choose delivery from configuration; callers do not depend on a vendor."""
    if getattr(settings, "BREVO_API_KEY", "") and getattr(settings, "BREVO_SENDER_EMAIL", ""):
        return BrevoEmailAdapter()
    if getattr(settings, "EMAIL_HOST_USER", ""):
        return SmtpEmailAdapter()
    return ConsoleEmailAdapter()
