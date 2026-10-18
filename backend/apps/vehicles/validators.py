"""Validation rules for Indian vehicle registration and compliance identifiers."""

import re

from django.core.exceptions import ValidationError


_STANDARD_REGISTRATION = re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$")
_BH_REGISTRATION = re.compile(r"^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$")
_CHASSIS_NUMBER = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
_POLICY_NUMBER = re.compile(r"^[A-Z0-9](?:[A-Z0-9/-]{3,38}[A-Z0-9])$")


def normalize_registration(value, label="Vehicle registration number"):
    number = re.sub(r"[\s-]", "", str(value or "")).upper()
    if not (_STANDARD_REGISTRATION.fullmatch(number) or _BH_REGISTRATION.fullmatch(number)):
        raise ValidationError(
            f"{label} must match an Indian registration format, e.g. UK07AB1234 or 24BH1234AA."
        )
    return number


def normalize_chassis_number(value):
    number = re.sub(r"\s", "", str(value or "")).upper()
    if not _CHASSIS_NUMBER.fullmatch(number):
        raise ValidationError(
            "Chassis number must be exactly 17 letters/digits; I, O and Q are not used in VINs."
        )
    return number


def normalize_policy_number(value):
    number = re.sub(r"\s", "", str(value or "")).upper()
    if not _POLICY_NUMBER.fullmatch(number) or not any(char.isdigit() for char in number):
        raise ValidationError(
            "Enter a valid insurance policy number (5–40 letters/digits, optionally using / or -)."
        )
    return number
