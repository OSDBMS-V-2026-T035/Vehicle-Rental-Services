"""Directions-provider boundary used by customer and shop search results."""

from urllib.parse import urlencode

from django.conf import settings


class GoogleMapsDirectionsAdapter:
    """Build a Google Maps directions URL without coupling views to its format."""

    def directions_url(self, latitude, longitude):
        base_url = getattr(settings, "MAPS_DIRECTIONS_URL", "https://www.google.com/maps/dir/")
        return f"{base_url}?{urlencode({'api': 1, 'destination': f'{latitude},{longitude}'})}"


def get_directions_adapter():
    """Single replacement point when a different maps provider is adopted."""
    return GoogleMapsDirectionsAdapter()
