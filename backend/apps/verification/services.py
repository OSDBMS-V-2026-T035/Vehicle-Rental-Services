"""Small, provider-independent identity validation helpers."""

import re

from django.contrib.auth.hashers import make_password


# The complete Aadhaar number is never persisted and this is not a government
# KYC lookup. We only check the requested 12-digit shape and reject obvious
# repeated-digit placeholders before retaining a password hash and final four
# digits for the booking.
# A PAN has five letters (the fourth is the holder-status code), followed by
# four digits and one final letter. Keep the same complete PAN structure in a
# GSTIN after its two-character state code.
_PAN = re.compile(r"^[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]$")
_GSTIN = re.compile(r"^(?:0[1-9]|[12][0-9]|3[0-8]|97)[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z][0-9A-Z]Z[A-Z0-9]$")


def validate_pan(value):
    return bool(_PAN.fullmatch(str(value or "").strip().upper()))


def validate_gstin(value):
    return bool(_GSTIN.fullmatch(str(value or "").strip().upper()))


def validate_aadhaar_last4(value):
    return bool(re.fullmatch(r"[0-9]{4}", str(value or "").strip()))


def validate_aadhaar(value):
    digits = re.sub(r"[\s-]", "", str(value or ""))
    if not re.fullmatch(r"[0-9]{12}", digits):
        return False, None
    if re.search(r"([0-9])\1{5,}", digits):
        return False, None
    return True, (make_password(digits), digits[-4:])
