from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from .views import _booking_redirect


class BookingRedirectTests(SimpleTestCase):
    def test_preserves_a_valid_local_checkout_handoff(self):
        pickup = timezone.localdate() + timedelta(days=1)
        return_date = pickup + timedelta(days=2)
        result = _booking_redirect(
            f"/user-portal/?vehicle_id=42&pickup_date={pickup}&return_date={return_date}&ignored=value"
        )
        self.assertEqual(
            result,
            f"/user-portal/?vehicle_id=42&pickup_date={pickup}&return_date={return_date}&checkout=1",
        )

    def test_rejects_external_or_invalid_booking_redirects(self):
        self.assertEqual(_booking_redirect("https://example.com/user-portal/?vehicle_id=1"), "/user-portal/")
        self.assertEqual(_booking_redirect("/user-portal/?vehicle_id=0&pickup_date=2026-01-01&return_date=2026-01-02"), "/user-portal/")
        self.assertEqual(_booking_redirect("/user-portal/?vehicle_id=1&pickup_date=not-a-date&return_date=2026-01-02"), "/user-portal/")

