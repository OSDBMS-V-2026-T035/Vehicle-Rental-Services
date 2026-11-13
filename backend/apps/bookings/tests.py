from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.db.models import Count, Q
from django.db import OperationalError
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from unittest.mock import Mock, patch
from apps.payments.models import PaymentTransaction

from .documents import _document_bytes
from .models import Booking, BookingChange
from .policy import cancellation_refund_percent, refund_amount
from .handover import CHECKLIST_FIELDS, validate_inspection_payload
from .services import active_reservation_statuses, create_checkout_booking


class BookingCancellationPolicyTests(SimpleTestCase):
    def test_refund_tiers_match_the_published_windows(self):
        pickup = date(2026, 12, 10)
        self.assertEqual(cancellation_refund_percent(pickup, date(2026, 12, 5)), 100)
        self.assertEqual(cancellation_refund_percent(pickup, date(2026, 12, 7)), 80)
        self.assertEqual(cancellation_refund_percent(pickup, date(2026, 12, 9)), 50)
        self.assertEqual(cancellation_refund_percent(pickup, date(2026, 12, 10)), 0)

    def test_refund_rounds_to_paise(self):
        self.assertEqual(refund_amount(Decimal("499.99"), 80), Decimal("399.99"))


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


class RuntimeVerificationTests(TestCase):
    def test_runtime_verification_accepts_the_current_migrated_schema(self):
        call_command("verify_runtime")


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

    def test_pending_extension_holds_only_additional_dates_and_never_double_counts(self):
        from .services import active_reservation_count

        pickup = date.today() + timedelta(days=4)
        booking = Booking.objects.create(
            customer=self.customer, vehicle=self.vehicle, pickup_date=pickup,
            return_date=pickup + timedelta(days=1), total_amount="1000.00",
            status=Booking.Status.CONFIRMED,
        )
        BookingChange.objects.create(
            booking=booking, requested_by=self.customer,
            kind=BookingChange.Kind.EXTEND, status=BookingChange.Status.PENDING_PAYMENT,
            from_pickup=pickup, from_return=booking.return_date,
            to_pickup=pickup, to_return=pickup + timedelta(days=3),
            amount="2000.00", expires_at=timezone.now() + timedelta(minutes=10),
        )

        self.assertEqual(active_reservation_count(
            vehicle_id=self.vehicle.id, pickup_date=pickup, return_date=booking.return_date,
        ), 1)
        self.assertEqual(active_reservation_count(
            vehicle_id=self.vehicle.id, pickup_date=booking.return_date + timedelta(days=1),
            return_date=pickup + timedelta(days=3),
        ), 1)


class BookingLifecycleIntegrationTests(TestCase):
    def setUp(self):
        from apps.accounts.models import ShopkeeperProfile, User
        from apps.payments.models import PaymentTransaction
        from apps.vehicles.models import Vehicle

        owner = User.objects.create_user(
            email="lifecycle-shop@example.com", phone_number="9876543230", password="safe-test-pass",
            role=User.Role.SHOPKEEPER, is_email_verified=True,
        )
        shop = ShopkeeperProfile.objects.create(
            user=owner, shop_name="Lifecycle Rentals", shop_address="Dehradun",
            verification_status=ShopkeeperProfile.VerificationStatus.VERIFIED,
        )
        self.customer = User.objects.create_user(
            email="lifecycle-renter@example.com", phone_number="9876543231", password="safe-test-pass",
            is_email_verified=True,
        )
        self.vehicle = Vehicle.objects.create(
            shopkeeper=shop, vehicle_type=Vehicle.VehicleType.SCOOTER,
            brand="Test", model_name="Scooter", registration_number="UK07XY1234",
            manufacturing_year=2024, daily_rate="500.00",
            listing_status=Vehicle.ListingStatus.APPROVED,
        )
        self.pickup = timezone.localdate() + timedelta(days=5)
        self.booking = Booking.objects.create(
            customer=self.customer, vehicle=self.vehicle, pickup_date=self.pickup,
            return_date=self.pickup + timedelta(days=2), total_amount="1000.00",
            daily_rate_snapshot="500.00", status=Booking.Status.CONFIRMED,
            commissionable_base="1000.00", commission_rate="10.00",
            platform_commission="100.00", shopkeeper_net_earnings="900.00",
            financial_confirmed_at=timezone.now(),
        )
        self.payment = PaymentTransaction.objects.create(
            booking=self.booking, customer=self.customer, amount="1000.00",
            status=PaymentTransaction.Status.PAID, provider="RAZORPAY",
            provider_payment_id="pay_lifecycle_1", provider_reference="order_lifecycle_1",
        )

    def test_extension_uses_frozen_daily_rate_and_updates_financial_snapshot(self):
        from .lifecycle import apply_paid_extension, prepare_extension

        booking, change = prepare_extension(
            customer=self.customer, booking_id=self.booking.id,
            new_return=self.booking.return_date + timedelta(days=1),
        )
        self.assertEqual(change.amount, Decimal("500.00"))
        self.assertEqual(change.status, BookingChange.Status.PENDING_PAYMENT)
        booking = apply_paid_extension(change_id=change.id, provider_payment_id="pay_extension_1")
        booking.refresh_from_db()
        change.refresh_from_db()
        self.assertEqual(booking.return_date, self.pickup + timedelta(days=3))
        self.assertEqual(booking.total_amount, Decimal("1500.00"))
        self.assertEqual(booking.platform_commission, Decimal("150.00"))
        self.assertEqual(change.status, BookingChange.Status.COMPLETED)

    def test_reschedule_preserves_duration_without_repricing(self):
        from .lifecycle import prepare_reschedule

        new_pickup = timezone.localdate() + timedelta(days=10)
        booking, change = prepare_reschedule(
            customer=self.customer, booking_id=self.booking.id, new_pickup=new_pickup,
        )
        self.assertEqual(booking.pickup_date, new_pickup)
        self.assertEqual(booking.return_date, new_pickup + timedelta(days=2))
        self.assertEqual(booking.total_amount, Decimal("1000.00"))
        self.assertEqual(change.status, BookingChange.Status.COMPLETED)

    @patch("apps.bookings.cancellations.get_payment_gateway")
    def test_customer_cancellation_applies_full_five_day_refund(self, get_gateway):
        from .cancellations import cancel_booking

        gateway = get_gateway.return_value
        gateway.refund.return_value = {
            "id": "rfnd_lifecycle_1", "payment_id": "pay_lifecycle_1",
            "amount": 100000, "status": "pending",
        }
        change, completed = cancel_booking(
            booking_id=self.booking.id, actor=self.customer, customer_request=True,
        )
        self.booking.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertTrue(completed)
        self.assertEqual(change.refund_percent, 100)
        self.assertEqual(change.refunded_amount, Decimal("1000.00"))
        self.assertEqual(self.booking.status, Booking.Status.CANCELLED)
        self.assertEqual(self.payment.status, PaymentTransaction.Status.REFUNDED)
        self.assertEqual(self.booking.commissionable_base, Decimal("0.00"))
        gateway.refund.assert_called_once()

    @patch("apps.bookings.cancellations.get_payment_gateway")
    def test_three_day_cancellation_refunds_eighty_percent(self, get_gateway):
        from .cancellations import cancel_booking

        self.booking.pickup_date = timezone.localdate() + timedelta(days=3)
        self.booking.save(update_fields=["pickup_date"])
        gateway = get_gateway.return_value
        gateway.refund.return_value = {
            "id": "rfnd_lifecycle_2", "payment_id": "pay_lifecycle_1",
            "amount": 80000, "status": "pending",
        }
        change, completed = cancel_booking(
            booking_id=self.booking.id, actor=self.customer, customer_request=True,
        )
        self.payment.refresh_from_db()
        self.assertTrue(completed)
        self.assertEqual(change.refund_percent, 80)
        self.assertEqual(change.refunded_amount, Decimal("800.00"))
        self.assertEqual(self.payment.status, PaymentTransaction.Status.PARTIALLY_REFUNDED)

    @patch("apps.bookings.cancellations.get_payment_gateway")
    def test_one_day_cancellation_refunds_fifty_percent(self, get_gateway):
        from .cancellations import cancel_booking

        self.booking.pickup_date = timezone.localdate() + timedelta(days=1)
        self.booking.save(update_fields=["pickup_date"])
        get_gateway.return_value.refund.return_value = {
            "id": "rfnd_lifecycle_3", "payment_id": "pay_lifecycle_1",
            "amount": 50000, "status": "pending",
        }
        change, completed = cancel_booking(
            booking_id=self.booking.id, actor=self.customer, customer_request=True,
        )
        self.assertTrue(completed)
        self.assertEqual(change.refund_percent, 50)
        self.assertEqual(change.refunded_amount, Decimal("500.00"))

    @patch("apps.payments.views.apply_paid_extension", side_effect=ValueError("Capacity changed."))
    def test_captured_extension_that_cannot_be_applied_is_refunded(self, apply_extension):
        from apps.payments.views import _finalize_extension_payment
        from .lifecycle import prepare_extension

        _, change = prepare_extension(
            customer=self.customer, booking_id=self.booking.id,
            new_return=self.booking.return_date + timedelta(days=1),
        )
        change.provider_order_id = "order_extension_unapplied"
        change.save(update_fields=["provider_order_id"])
        gateway = Mock()
        gateway.fetch_payment.return_value = {
            "id": "pay_extension_unapplied", "order_id": change.provider_order_id,
            "amount": 50000, "currency": "INR", "status": "captured",
        }
        gateway.refund.return_value = {
            "id": "rfnd_extension_unapplied", "payment_id": "pay_extension_unapplied",
            "amount": 50000, "status": "pending",
        }
        with self.assertRaisesMessage(ValueError, "A refund has been initiated"):
            _finalize_extension_payment(gateway, change, "pay_extension_unapplied")
        change.refresh_from_db()
        self.assertEqual(change.status, BookingChange.Status.FAILED)
        self.assertEqual(change.refunded_amount, Decimal("500.00"))
        self.assertEqual(change.refunds.get().status, "INITIATED")
        apply_extension.assert_called_once()

    @patch("apps.bookings.cancellations.get_payment_gateway")
    def test_same_day_cancellation_does_not_call_gateway(self, get_gateway):
        from .cancellations import cancel_booking

        self.booking.pickup_date = timezone.localdate()
        self.booking.save(update_fields=["pickup_date"])
        change, completed = cancel_booking(
            booking_id=self.booking.id, actor=self.customer, customer_request=True,
        )
        self.assertTrue(completed)
        self.assertEqual(change.refund_percent, 0)
        self.assertEqual(change.refunded_amount, Decimal("0.00"))
        get_gateway.assert_not_called()

    @patch("apps.bookings.cancellations.get_payment_gateway")
    def test_refund_retry_reuses_the_same_gateway_receipt(self, get_gateway):
        from .cancellations import cancel_booking

        gateway = get_gateway.return_value
        gateway.refund.side_effect = [RuntimeError("timeout"), {
            "id": "rfnd_retry", "payment_id": "pay_lifecycle_1", "amount": 100000, "status": "pending",
        }]
        first, completed = cancel_booking(
            booking_id=self.booking.id, actor=self.customer, customer_request=True,
        )
        self.assertFalse(completed)
        refund = first.refunds.get()
        first_receipt = refund.receipt
        second, completed = cancel_booking(
            booking_id=self.booking.id, actor=self.customer, customer_request=True,
        )
        self.assertTrue(completed)
        self.assertEqual(second.refunds.get().receipt, first_receipt)
        self.assertEqual(gateway.refund.call_args_list[0].args[1]["receipt"], first_receipt)
        self.assertEqual(gateway.refund.call_args_list[1].args[1]["receipt"], first_receipt)

    @patch("apps.bookings.cancellations.get_payment_gateway")
    def test_provider_declined_refund_retries_with_a_new_receipt(self, get_gateway):
        from .cancellations import cancel_booking

        gateway = get_gateway.return_value
        gateway.refund.side_effect = [{
            "id": "rfnd_declined", "payment_id": "pay_lifecycle_1",
            "amount": 100000, "status": "failed",
        }, {
            "id": "rfnd_retry_ok", "payment_id": "pay_lifecycle_1",
            "amount": 100000, "status": "pending",
        }]
        first, completed = cancel_booking(
            booking_id=self.booking.id, actor=self.customer, customer_request=True,
        )
        self.assertFalse(completed)
        refund = first.refunds.get()
        failed_receipt = refund.receipt
        gateway.list_refunds.return_value = {"items": [{
            "id": "rfnd_declined", "receipt": failed_receipt, "status": "failed",
        }]}
        second, completed = cancel_booking(
            booking_id=self.booking.id, actor=self.customer, customer_request=True,
        )
        refund.refresh_from_db()
        self.assertTrue(completed)
        self.assertNotEqual(refund.receipt, failed_receipt)
        self.assertEqual(gateway.refund.call_args_list[1].args[1]["receipt"], refund.receipt)


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

