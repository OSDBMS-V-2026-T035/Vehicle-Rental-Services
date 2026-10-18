from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from .documents import _document_bytes
from .models import Booking
from .services import active_reservation_statuses


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

