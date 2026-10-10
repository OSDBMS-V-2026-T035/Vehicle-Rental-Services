import base64
import random
import secrets
from datetime import timedelta
from html import escape

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from .models import CaptchaChallenge

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def create_captcha():
    answer = "".join(secrets.choice(ALPHABET) for _ in range(5))
    challenge = CaptchaChallenge.objects.create(
        challenge_id=secrets.token_urlsafe(24),
        answer_hash=make_password(answer),
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    lines = "".join(f'<line x1="{random.randrange(0, 360)}" y1="{random.randrange(0, 120)}" x2="{random.randrange(0, 360)}" y2="{random.randrange(0, 120)}" stroke="#5c7891" stroke-width="1"/>' for _ in range(10))
    chars = "".join(f'<text x="{18 + index * 65}" y="78" font-size="58" font-family="Arial, sans-serif" font-weight="700" fill="#ffffff" transform="rotate({random.randrange(-9, 10)} {18 + index * 65} 78)">{escape(char)}</text>' for index, char in enumerate(answer))
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="360" height="120" viewBox="0 0 360 120"><rect width="360" height="120" rx="12" fill="#102d4c"/>{lines}{chars}</svg>'
    image = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return {"captcha_id": challenge.challenge_id, "image": image, "expires_in": 300}


def verify_captcha(challenge_id, answer):
    challenge = CaptchaChallenge.objects.filter(challenge_id=str(challenge_id or ""), used_at__isnull=True).first()
    if not challenge or challenge.expires_at <= timezone.now():
        return False
    challenge.used_at = timezone.now()
    challenge.save(update_fields=["used_at"])
    return bool(answer) and check_password(str(answer).strip().upper(), challenge.answer_hash)
