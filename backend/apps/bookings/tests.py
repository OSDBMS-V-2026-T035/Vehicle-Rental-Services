from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.db.models import Count, Q
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from unittest.mock import patch

from .documents import _document_bytes
from .models import Booking
from .handover import CHECKLIST_FIELDS, validate_inspection_payload
from .services import active_reservation_statuses, create_checkout_booking


class BookingDocumentTests(SimpleTestCase):
    def _booking(self):
        now = timezone.make_aware(datetime(2026, 10, 18, 10, 30))
        shop_user = SimpleNamespace(phone_number="9876543210")
        shop = SimpleNamespace(
            shop_name="Himalayan Motors", shop_address="Mall Road, Dehradun",
            proprietor_name="Rohan Mehta", gstin="05ABCDE1234F1Z5", user=shop_user,
        )
        vehicle = SimpleNamespace(
            display_name="Maruti Swift", shopkeeper=shop, registration_number="UK07AB1234",
            get_vehicle_type_display=lambda: "Car", body_style="hatchback", fuel_type="petrol",
            manufacturing_year=2024, seating_capacity=5, daily_rate=Decimal("1600.00"),
        )
        customer = SimpleNamespace(get_full_name=lambda: "Aarav Sharma", email="aarav@example.com", phone_number="9123456789")
        payment = SimpleNamespace(
            id=42, amount=Decimal("4800.00"), currency="INR", provider="RAZORPAY",
            provider_payment_id="pay_demo_123", provider_reference="order_demo_123", updated_at=now,
        )
        return SimpleNamespace(
            id=7, payment=payment, vehicle=vehicle, customer=customer,
            renter_full_name="Aarav Sharma", renter_phone="9123456789", renter_email="aarav@example.com",
            renter_age=29, renter_gender="Male", pickup_date=date(2026, 11, 1),
            return_date=date(2026, 11, 3), created_at=now,
        )

    def test_receipt_and_confirmation_are_valid_branded_pdfs(self):
        booking = self._booking()
        for kind, phrase in (("receipt", b"Payment Receipt"), ("confirmation", b"Ride Confirmation")):
            content = _document_bytes(booking, kind)
            self.assertTrue(content.startswith(b"%PDF"))
            self.assertIn(phrase, content)
            self.assertIn(b"RideHub", content)


class ActiveReservationStatusTests(SimpleTestCase):
    def test_confirmed_and_handed_over_bookings_both_consume_inventory(self):
        self.assertEqual(
            active_reservation_statuses(),
            (Booking.Status.CONFIRMED, Booking.Status.HANDED_OVER),
        )

    def test_completed_and_cancelled_bookings_do_not_consume_inventory(self):
        self.assertNotIn(Booking.Status.COMPLETED, active_reservation_statuses())
        self.assertNotIn(Booking.Status.CANCELLED, active_reservation_statuses())


class CheckoutRetryTests(SimpleTestCase):
    def test_retries_a_mysql_deadlock_once(self):
        expected = object()
        with patch("apps.bookings.services._create_checkout_booking", side_effect=[OperationalError(1213, "deadlock"), expected]) as create:
            self.assertIs(create_checkout_booking(example="value"), expected)

        self.assertEqual(create.call_count, 2)

    def test_does_not_retry_a_non_lock_database_error(self):
        with patch("apps.bookings.services._create_checkout_booking", side_effect=OperationalError(2003, "connection failed")) as create:
            with self.assertRaises(OperationalError):
                create_checkout_booking(example="value")

        self.assertEqual(create.call_count, 1)


class ActiveReservationQueryTests(TestCase):
    def setUp(self):
        from apps.accounts.models import ShopkeeperProfile, User
        from apps.vehicles.models import Vehicle

        owner = User.objects.create_user(
            email="shop@example.com", phone_number="9876543210", password="safe-test-pass",
            role=User.Role.SHOPKEEPER, is_email_verified=True,
        )
        shop = ShopkeeperProfile.objects.create(
            user=owner, shop_name="Test Rentals", shop_address="Dehradun",
            verification_status=ShopkeeperProfile.VerificationStatus.VERIFIED,
        )
        self.customer = User.objects.create_user(
            email="renter@example.com", phone_number="9876543211", password="safe-test-pass",
            is_email_verified=True,
        )
        self.vehicle = Vehicle.objects.create(
            shopkeeper=shop, vehicle_type=Vehicle.VehicleType.CAR, brand="Test",
            model_name="Car", registration_number="UK07AB1234", manufacturing_year=2024,
            daily_rate="1000.00", listing_status=Vehicle.ListingStatus.APPROVED,
        )

    def test_only_confirmed_handed_over_and_live_pending_holds_block_search(self):
        from django.utils import timezone

        from .services import active_reservation_filter

        pickup = date.today() + timedelta(days=2)
        common = {
            "customer": self.customer, "vehicle": self.vehicle,
            "pickup_date": pickup, "return_date": pickup + timedelta(days=1),
            "total_amount": "1000.00",
        }
        Booking.objects.create(**common, status=Booking.Status.CONFIRMED)
        Booking.objects.create(**common, status=Booking.Status.HANDED_OVER)
        Booking.objects.create(
            **common, status=Booking.Status.PENDING,
            payment_expires_at=timezone.now() + timedelta(minutes=5),
        )
        Booking.objects.create(
            **common, status=Booking.Status.PENDING,
            payment_expires_at=timezone.now() - timedelta(minutes=1),
        )
        Booking.objects.create(**common, status=Booking.Status.CANCELLED)
        Booking.objects.create(**common, status=Booking.Status.COMPLETED)

        reserved = Booking.objects.filter(vehicle=self.vehicle).filter(active_reservation_filter())

        self.assertEqual(reserved.count(), 3)

    def test_relation_prefix_supports_vehicle_availability_aggregate(self):
        from .services import active_reservation_filter
        from apps.vehicles.models import Vehicle

        pickup = date.today() + timedelta(days=2)
        Booking.objects.create(
            customer=self.customer, vehicle=self.vehicle, pickup_date=pickup,
            return_date=pickup + timedelta(days=1), total_amount="1000.00",
            status=Booking.Status.CONFIRMED,
        )

        vehicle = Vehicle.objects.annotate(
            reserved_units=Count(
                "bookings",
                filter=Q(bookings__pickup_date__lte=pickup + timedelta(days=1))
                & Q(bookings__return_date__gte=pickup)
                & active_reservation_filter(relation_prefix="bookings__"),
            )
        ).get(pk=self.vehicle.pk)

        self.assertEqual(vehicle.reserved_units, 1)


class HandoverInspectionValidationTests(SimpleTestCase):
    def _payload(self):
        return {
            "odometer_km": "12345",
            "fuel_percent": "76",
            "condition_checklist": {field: True for field in CHECKLIST_FIELDS},
            "notes": "  Clean   condition  ",
        }

    def test_normalizes_handover_inspection_values(self):
        self.assertEqual(validate_inspection_payload(self._payload()), {
            "odometer_km": 12345,
            "fuel_percent": 76,
            "condition_checklist": {field: True for field in CHECKLIST_FIELDS},
            "notes": "Clean condition",
        })

    def test_requires_every_boolean_checklist_item(self):
        payload = self._payload()
        payload["condition_checklist"].pop("brakes")
        with self.assertRaisesMessage(ValueError, "Complete every vehicle condition checklist item."):
            validate_inspection_payload(payload)

    def test_rejects_out_of_range_meter_or_fuel_values(self):
        payload = self._payload()
        payload["fuel_percent"] = "101"
        with self.assertRaisesMessage(ValueError, "Fuel/battery level must be a whole percentage from 0 to 100."):
            validate_inspection_payload(payload)

    def test_rejects_non_boolean_checklist_values_and_oversized_notes(self):
        payload = self._payload()
        payload["condition_checklist"]["lights"] = "yes"
        with self.assertRaisesMessage(ValueError, "Every checklist item must be marked as passed or needs attention."):
            validate_inspection_payload(payload)
        payload = self._payload()
        payload["notes"] = "x" * 1001
        with self.assertRaisesMessage(ValueError, "Inspection notes must be 1,000 characters or fewer."):
            validate_inspection_payload(payload)


class HandoverWorkflowTests(TestCase):
    def setUp(self):
        from apps.accounts.models import ShopkeeperProfile, User
        from apps.payments.models import PaymentTransaction
        from apps.vehicles.models import Vehicle

        self.shopkeeper_user = User.objects.create_user(
            email="handover-shop@example.com", phone_number="9876543220", password="safe-test-pass",
            role=User.Role.SHOPKEEPER, is_email_verified=True,
        )
        self.shop = ShopkeeperProfile.objects.create(
            user=self.shopkeeper_user, shop_name="Inspection Rentals", shop_address="Dehradun",
            verification_status=ShopkeeperProfile.VerificationStatus.VERIFIED,
        )
        self.customer = User.objects.create_user(
            email="handover-renter@example.com", phone_number="9876543221", password="safe-test-pass",
            is_email_verified=True,
        )
        vehicle = Vehicle.objects.create(
            shopkeeper=self.shop, vehicle_type=Vehicle.VehicleType.CAR, brand="Test",
            model_name="Handover", registration_number="UK07CD1234", manufacturing_year=2024,
            daily_rate="1000.00", listing_status=Vehicle.ListingStatus.APPROVED,
        )
        pickup = date.today() + timedelta(days=1)
        self.booking = Booking.objects.create(
            customer=self.customer, vehicle=vehicle, pickup_date=pickup,
            return_date=pickup + timedelta(days=2), total_amount="2000.00",
            status=Booking.Status.CONFIRMED,
        )
        PaymentTransaction.objects.create(
            booking=self.booking, customer=self.customer, amount="2000.00",
            status=PaymentTransaction.Status.PAID,
        )
        self.vehicle = vehicle

    def _inspection_payload(self):
        return {
            "odometer_km": 12500,
            "fuel_percent": 80,
            "condition_checklist": {field: True for field in CHECKLIST_FIELDS},
            "notes": "Pickup condition reviewed with renter.",
        }

    def test_pickup_and_return_codes_are_one_time_and_record_both_inspections(self):
        from .handover import issue_handover_code, record_handover_inspection
        from .models import BookingInspection

        pickup = issue_handover_code(
            customer=self.customer, booking_id=self.booking.id, stage=BookingInspection.Stage.PICKUP,
        )
        saved_pickup = BookingInspection.objects.get(booking=self.booking, stage=BookingInspection.Stage.PICKUP)
        self.assertNotEqual(saved_pickup.code_hash, pickup["code"])
        record_handover_inspection(
            profile=self.shop, booking_id=self.booking.id, stage=BookingInspection.Stage.PICKUP,
            code=pickup["code"], payload=self._inspection_payload(),
        )
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.HANDED_OVER)
        self.assertIsNotNone(self.booking.handover_at)

        returned = issue_handover_code(
            customer=self.customer, booking_id=self.booking.id, stage=BookingInspection.Stage.RETURN,
        )
        return_payload = self._inspection_payload() | {"odometer_km": 12640, "fuel_percent": 54}
        record_handover_inspection(
            profile=self.shop, booking_id=self.booking.id, stage=BookingInspection.Stage.RETURN,
            code=returned["code"], payload=return_payload,
        )
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.COMPLETED)
        self.assertIsNotNone(self.booking.received_back_at)
        self.assertEqual(
            BookingInspection.objects.filter(booking=self.booking, status=BookingInspection.Status.CONFIRMED).count(),
            2,
        )

    def test_wrong_code_attempt_is_saved_and_valid_code_is_single_use(self):
        from .handover import issue_handover_code, record_handover_inspection
        from .models import BookingInspection

        challenge = issue_handover_code(
            customer=self.customer, booking_id=self.booking.id, stage=BookingInspection.Stage.PICKUP,
        )
        with self.assertRaisesMessage(ValueError, "Handover code is incorrect."):
            record_handover_inspection(
                profile=self.shop, booking_id=self.booking.id, stage=BookingInspection.Stage.PICKUP,
                code="000000" if challenge["code"] != "000000" else "000001",
                payload=self._inspection_payload(),
            )
        inspection = BookingInspection.objects.get(booking=self.booking)
        self.assertEqual(inspection.attempts, 1)
        record_handover_inspection(
            profile=self.shop, booking_id=self.booking.id, stage=BookingInspection.Stage.PICKUP,
            code=challenge["code"], payload=self._inspection_payload(),
        )
        with self.assertRaisesMessage(ValueError, "This booking is not at the selected handover stage."):
            record_handover_inspection(
                profile=self.shop, booking_id=self.booking.id, stage=BookingInspection.Stage.PICKUP,
                code=challenge["code"], payload=self._inspection_payload(),
            )

    def test_expired_code_is_consumed_without_changing_booking_state(self):
        from django.utils import timezone

        from .handover import issue_handover_code, record_handover_inspection
        from .models import BookingInspection

        challenge = issue_handover_code(
            customer=self.customer, booking_id=self.booking.id, stage=BookingInspection.Stage.PICKUP,
        )
        with self.assertRaisesMessage(ValueError, "Handover code expired."):
            record_handover_inspection(
                profile=self.shop, booking_id=self.booking.id, stage=BookingInspection.Stage.PICKUP,
                code=challenge["code"], payload=self._inspection_payload(),
                now=timezone.now() + timedelta(minutes=11),
            )
        self.booking.refresh_from_db()
        inspection = BookingInspection.objects.get(booking=self.booking)
        self.assertEqual(self.booking.status, Booking.Status.CONFIRMED)
        self.assertEqual(inspection.status, BookingInspection.Status.EXPIRED)

    def test_handover_qr_contains_only_the_short_lived_stage_payload(self):
        from .handover import handover_qr_svg

        svg = handover_qr_svg(
            booking_id=self.booking.id,
            stage="PICKUP",
            code="123456",
        )

        self.assertIn("<svg", svg)
        self.assertNotIn("handover-renter@example.com", svg)

