from django.conf import settings


def integration_settings(request):
    """Expose browser-safe integration settings to the frontend templates."""

    return {
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    }
