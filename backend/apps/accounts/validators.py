import re

from django.core.exceptions import ValidationError


class StrongPasswordValidator:
    """Enforce the password rules used by both the API and the UI."""

    def validate(self, password, user=None):
        errors = []
        if len(password) < 10:
            errors.append("at least 10 characters")
        if not re.search(r"[A-Z]", password):
            errors.append("one uppercase letter")
        if not re.search(r"[a-z]", password):
            errors.append("one lowercase letter")
        if not re.search(r"\d", password):
            errors.append("one number")
        if not re.search(r"[^A-Za-z0-9\s]", password):
            errors.append("one special character")
        if re.search(r"\s", password):
            errors.append("no spaces")
        if errors:
            raise ValidationError("Password must contain " + ", ".join(errors) + ".")
        if user:
            identifier_values = [user.email, user.phone_number, user.first_name, user.last_name]
            lowered = password.lower()
            if any(value and len(value) >= 4 and value.lower() in lowered for value in identifier_values):
                raise ValidationError("Password must not contain your email, phone number, or name.")

    def get_help_text(self):
        return "Use 10+ characters with uppercase, lowercase, number, special character, and no spaces."
