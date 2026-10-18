from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import resolve

from .views import _search_filters, _validate_vehicle_image, _vehicle_payload
from .validators import normalize_chassis_number, normalize_policy_number, normalize_registration
from .matching import rank_vehicle_matches


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


class MarketplaceSearchFilterTests(SimpleTestCase):
    def test_parses_budget_seats_and_fuel(self):
        filters, error = _search_filters({"max_daily_rate": "1250.50", "min_seats": "4", "fuel_type": "diesel"})
        self.assertIsNone(error)
        self.assertEqual(str(filters["max_daily_rate"]), "1250.50")
        self.assertEqual(filters["min_seats"], 4)
        self.assertEqual(filters["fuel_type"], "diesel")

    def test_empty_filters_do_not_constrain_search(self):
        self.assertEqual(_search_filters({}), ({}, None))

    def test_rejects_malformed_or_non_finite_budget(self):
        for value in ("abc", "NaN", "Infinity", "-1"):
            with self.subTest(value=value):
                filters, error = _search_filters({"max_daily_rate": value})
                self.assertIsNone(filters)
                self.assertTrue(error)


class VehicleMatchingTests(SimpleTestCase):
    def setUp(self):
        self.vehicles = [
            {"id": 1, "name": "Near but reserved", "available_quantity": 0, "daily_rate": "500", "distance_km": 1},
            {"id": 2, "name": "Far and cheap", "available_quantity": 2, "daily_rate": "300", "distance_km": 8},
            {"id": 3, "name": "Nearby", "available_quantity": 1, "daily_rate": "700", "distance_km": 2},
        ]

    def test_recommended_prioritizes_available_units_then_proximity(self):
        result = rank_vehicle_matches(self.vehicles)
        self.assertEqual([row["id"] for row in result], [3, 2, 1])

    def test_nearest_and_price_sorts_are_explicit(self):
        self.assertEqual([row["id"] for row in rank_vehicle_matches(self.vehicles, "nearest")], [1, 3, 2])
        self.assertEqual([row["id"] for row in rank_vehicle_matches(self.vehicles, "price_low")], [2, 1, 3])
        self.assertEqual([row["id"] for row in rank_vehicle_matches(self.vehicles, "price_high")], [3, 1, 2])

    def test_invalid_sort_is_rejected(self):
        with self.assertRaises(ValueError):
            rank_vehicle_matches(self.vehicles, "random")

    def test_rejects_invalid_seat_count_and_fuel(self):
        for params in ({"min_seats": "4.5"}, {"min_seats": "101"}, {"fuel_type": "rocket"}):
            with self.subTest(params=params):
                filters, error = _search_filters(params)
                self.assertIsNone(filters)
                self.assertTrue(error)

