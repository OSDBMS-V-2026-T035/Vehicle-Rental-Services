from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import ShopkeeperProfile, User
from apps.adminpanel.models import CommissionConfiguration
from apps.bookings.finance import reverse_booking_commission, snapshot_booking_financials
from apps.bookings.models import Booking
from apps.vehicles.models import Vehicle


class BookingFinanceTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user(email="finance-shop@example.com", phone_number="9876543290", password="safe-test-pass", role=User.Role.SHOPKEEPER, is_email_verified=True)
        shop = ShopkeeperProfile.objects.create(user=owner, shop_name="Finance Rentals", shop_address="Dehradun", verification_status=ShopkeeperProfile.VerificationStatus.VERIFIED)
        customer = User.objects.create_user(email="finance-renter@example.com", phone_number="9876543291", password="safe-test-pass", is_email_verified=True)
        vehicle = Vehicle.objects.create(shopkeeper=shop, vehicle_type=Vehicle.VehicleType.CAR, brand="Test", model_name="Finance", registration_number="UK07EF1234", manufacturing_year=2024, daily_rate="999.99", listing_status=Vehicle.ListingStatus.APPROVED)
        self.booking = Booking.objects.create(customer=customer, vehicle=vehicle, pickup_date=date.today() + timedelta(days=1), return_date=date.today() + timedelta(days=2), total_amount="999.99")

    def test_snapshot_excludes_tax_and_is_immutable_after_rate_change(self):
        CommissionConfiguration.objects.create(commission_rate="10.00")
        snapshot_booking_financials(self.booking)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.commissionable_base, Decimal("999.99"))
        self.assertEqual(self.booking.tax_amount, Decimal("0.00"))
        self.assertEqual(self.booking.platform_commission, Decimal("100.00"))
        self.assertEqual(self.booking.shopkeeper_net_earnings, Decimal("899.99"))
        CommissionConfiguration.objects.create(commission_rate="12.00")
        snapshot_booking_financials(self.booking)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.commission_rate, Decimal("10.00"))

    def test_reversal_marks_history_without_deleting_snapshot(self):
        CommissionConfiguration.objects.create(commission_rate="0.00")
        snapshot_booking_financials(self.booking)
        reverse_booking_commission(self.booking)
        self.booking.refresh_from_db()
        self.assertIsNotNone(self.booking.commission_reversed_at)
        self.assertEqual(self.booking.platform_commission, Decimal("0.00"))
