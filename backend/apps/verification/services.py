"""Small, provider-independent identity validation helpers."""

import re

from django.contrib.auth.hashers import make_password


# The complete Aadhaar number is never persisted and this is not a government
# KYC lookup. We validate the 12-digit format with the Verhoeff checksum before
# retaining only a password hash and the final four digits for the booking.
_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)

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
    if not re.fullmatch(r"[0-9]{12}", digits) or digits[0] in {"0", "1"}:
        return False, None
    checksum = 0
    for index, digit in enumerate(reversed(digits)):
        checksum = _D[checksum][_P[index % 8][int(digit)]]
    if checksum != 0:
        return False, None
    return True, (make_password(digits), digits[-4:])
