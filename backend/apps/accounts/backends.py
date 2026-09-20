from django.contrib.auth import get_user_model


class EmailOrPhoneBackend:
    """Authenticate users by email or their verified-format phone number."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = (username or kwargs.get("email") or "").strip().lower()
        if not identifier or not password:
            return None

        User = get_user_model()
        lookup = {"email__iexact": identifier} if "@" in identifier else {"phone_number": identifier}
        try:
            user = User.objects.get(**lookup)
        except User.DoesNotExist:
            return None
        if user.check_password(password) and user.is_active:
            return user
        return None

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
