from types import SimpleNamespace

from django.test import SimpleTestCase

from .views import _vehicle_payload


class VehiclePayloadAvailabilityTests(SimpleTestCase):
    def setUp(self):
        shop = SimpleNamespace(shop_name="Example Rentals", shop_address="Dehradun", latitude=None, longitude=None)
        self.vehicle = SimpleNamespace(
            id=1,
            vehicle_type="car",
            brand="Example",
            model_name="City",
            registration_number="UK07AB1234",
            daily_rate="1200.00",
            seating_capacity=5,
            body_style="sedan",
            fuel_type="petrol",
            fuel_capacity="40.0",
            quantity=2,
            available_quantity=2,
            description="",
            listing_status="APPROVED",
            is_available=True,
            shopkeeper=shop,
            image=None,
            display_name="Example City",
        )

    def test_date_search_subtracts_reserved_units_from_fleet_quantity(self):
        payload = _vehicle_payload(self.vehicle, reserved_units=1)

        self.assertEqual(payload["quantity"], 2)
        self.assertEqual(payload["available_quantity"], 1)
        self.assertEqual(payload["availability_status"], "AVAILABLE")
        self.assertEqual(payload["availability_message"], "1 of 2 units available for these dates")

    def test_date_search_marks_fully_reserved_fleet_unavailable(self):
        payload = _vehicle_payload(self.vehicle, reserved_units=2)

        self.assertEqual(payload["available_quantity"], 0)
        self.assertEqual(payload["availability_status"], "UNAVAILABLE")
        self.assertEqual(payload["availability_message"], "Unavailable for these dates")

    def test_default_payload_reports_the_saved_inventory_quantity(self):
        payload = _vehicle_payload(self.vehicle)

        self.assertEqual(payload["available_quantity"], 2)
        self.assertEqual(payload["availability_status"], "AVAILABLE")

