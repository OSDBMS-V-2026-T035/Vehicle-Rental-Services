from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone

from .documents import _document_bytes


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

