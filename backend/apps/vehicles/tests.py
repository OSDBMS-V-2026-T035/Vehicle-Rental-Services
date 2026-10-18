from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import resolve

from .views import _validate_vehicle_image, _vehicle_payload
from .validators import normalize_chassis_number, normalize_policy_number, normalize_registration


class VehicleImageValidationTests(SimpleTestCase):
    def test_accepts_an_image_upload(self):
        upload = SimpleUploadedFile("vehicle.jpg", b"image-data", content_type="image/jpeg")

        _validate_vehicle_image(upload)

    def test_rejects_non_image_upload(self):
        upload = SimpleUploadedFile("vehicle.pdf", b"document-data", content_type="application/pdf")

        with self.assertRaisesMessage(ValidationError, "Vehicle photo must be an image file."):
            _validate_vehicle_image(upload)

    def test_rejects_an_image_larger_than_five_megabytes(self):
        upload = SimpleUploadedFile("vehicle.jpg", b"x" * (5 * 1024 * 1024 + 1), content_type="image/jpeg")

        with self.assertRaisesMessage(ValidationError, "Vehicle photo must be 5 MB or smaller."):
            _validate_vehicle_image(upload)


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

    def test_vehicle_detail_route_does_not_shadow_live_search(self):
        self.assertEqual(resolve("/api/vehicles/search/").url_name, "vehicles-search")
        self.assertEqual(resolve("/api/vehicles/17/").url_name, "vehicle-detail")


class IndianVehicleIdentifierValidationTests(SimpleTestCase):
    def test_normalizes_standard_indian_registration(self):
        self.assertEqual(normalize_registration(" uk07 ab 1234 "), "UK07AB1234")

    def test_accepts_bharat_series_registration(self):
        self.assertEqual(normalize_registration("24bh1234aa"), "24BH1234AA")

    def test_rejects_malformed_registration_instead_of_truncating_it(self):
        with self.assertRaises(ValidationError):
            normalize_registration("6544444444444444555555555555555555")

    def test_requires_a_17_character_vin_without_forbidden_letters(self):
        self.assertEqual(normalize_chassis_number("ma3ejkd1s00a12345"), "MA3EJKD1S00A12345")
        with self.assertRaises(ValidationError):
            normalize_chassis_number("MA3EJKD1S00A1234O")

    def test_normalizes_policy_number_and_requires_a_digit(self):
        self.assertEqual(normalize_policy_number(" ab/123-xy "), "AB/123-XY")
        with self.assertRaises(ValidationError):
            normalize_policy_number("POLICY")

