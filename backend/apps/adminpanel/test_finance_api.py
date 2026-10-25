import json
from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import ShopkeeperProfile, User
from apps.adminpanel.models import CommissionConfiguration
from apps.bookings.finance import reverse_booking_commission, snapshot_booking_financials
from apps.bookings.models import Booking
from apps.payments.models import PaymentTransaction
from apps.vehicles.models import Vehicle


class FinancialDashboardAPITests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email="finance-admin@example.com", phone_number="9876543100", password="safe-test-pass", role=User.Role.ADMIN, is_staff=True, is_email_verified=True)
        self.customer = User.objects.create_user(email="finance-customer@example.com", phone_number="9876543101", password="safe-test-pass", is_email_verified=True)
        self.shop_user = User.objects.create_user(email="finance-owner@example.com", phone_number="9876543102", password="safe-test-pass", role=User.Role.SHOPKEEPER, is_email_verified=True)
        self.shop = ShopkeeperProfile.objects.create(user=self.shop_user, shop_name="North Rentals", shop_address="Dehradun", verification_status=ShopkeeperProfile.VerificationStatus.VERIFIED)
        self.vehicle = Vehicle.objects.create(shopkeeper=self.shop, vehicle_type=Vehicle.VehicleType.CAR, brand="North", model_name="One", registration_number="UK07GH1234", manufacturing_year=2024, daily_rate="1000.00", listing_status=Vehicle.ListingStatus.APPROVED)
        CommissionConfiguration.objects.create(commission_rate="10.00", updated_by=self.admin)
        self.booking = self._booking(self.vehicle, "1000.00", PaymentTransaction.Status.PAID)

    def _booking(self, vehicle, amount, payment_status):
        booking = Booking.objects.create(customer=self.customer, vehicle=vehicle, pickup_date=date.today() + timedelta(days=2), return_date=date.today() + timedelta(days=3), total_amount=amount, status=Booking.Status.CONFIRMED)
        PaymentTransaction.objects.create(booking=booking, customer=self.customer, amount=amount, status=payment_status)
        if payment_status in {PaymentTransaction.Status.PAID, PaymentTransaction.Status.REFUNDED}:
            snapshot_booking_financials(booking)
        return booking

    def test_admin_revenue_uses_snapshots_and_excludes_pending_payment(self):
        self._booking(self.vehicle, "3000.00", PaymentTransaction.Status.PENDING)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin-revenue"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["summary"]["eligible_booking_fare"], "1000.00")
        self.assertEqual(data["summary"]["platform_commission"], "100.00")
        self.assertEqual(data["summary"]["shopkeeper_earnings"], "900.00")
        self.assertEqual(data["summary"]["eligible_bookings"], 1)
        self.assertEqual(data["summary"]["pending_payments"], 1)

    def test_reversal_is_preserved_but_removed_from_realized_revenue(self):
        reverse_booking_commission(self.booking)
        self.booking.payment.status = PaymentTransaction.Status.REFUNDED
        self.booking.payment.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.admin)
        data = self.client.get(reverse("admin-revenue")).json()
        self.assertEqual(data["summary"]["eligible_bookings"], 0)
        self.assertEqual(data["summary"]["commission_reversals"], "100.00")
        self.assertEqual(data["summary"]["net_platform_revenue"], "0.00")
        self.assertTrue(data["rows"][0]["reversed"])

    def test_non_admin_cannot_read_revenue_or_change_commission(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse("admin-revenue")).status_code, 403)
        response = self.client.post(reverse("admin-commission"), data=json.dumps({"commission_rate": "12"}), content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_shopkeeper_only_receives_own_earnings(self):
        other_user = User.objects.create_user(email="finance-owner2@example.com", phone_number="9876543103", password="safe-test-pass", role=User.Role.SHOPKEEPER, is_email_verified=True)
        other_shop = ShopkeeperProfile.objects.create(user=other_user, shop_name="South Rentals", shop_address="Dehradun", verification_status=ShopkeeperProfile.VerificationStatus.VERIFIED)
        other_vehicle = Vehicle.objects.create(shopkeeper=other_shop, vehicle_type=Vehicle.VehicleType.BIKE, brand="South", model_name="Two", registration_number="UK07IJ1234", manufacturing_year=2024, daily_rate="1200.00", listing_status=Vehicle.ListingStatus.APPROVED)
        other_booking = self._booking(other_vehicle, "1200.00", PaymentTransaction.Status.PAID)
        self.client.force_login(self.shop_user)
        data = self.client.get(reverse("shopkeeper-earnings"), {"vehicle_id": other_vehicle.id}).json()
        self.assertEqual(data["rows"], [])
        data = self.client.get(reverse("shopkeeper-earnings")).json()
        self.assertEqual([row["id"] for row in data["rows"]], [self.booking.id])
        self.assertNotIn(other_booking.id, [row["id"] for row in data["rows"]])

    def test_dedicated_checkout_route_requires_customer_authentication(self):
        target = reverse("booking-checkout-page") + "?vehicle_id=1&pickup_date=2030-01-01&return_date=2030-01-02&checkout=1"
        response = self.client.get(target)
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.customer)
        response = self.client.get(target)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "RIDEHUB_PORTAL")
