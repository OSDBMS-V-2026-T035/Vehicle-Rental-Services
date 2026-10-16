from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from .views import _amount_in_paise, _capture_and_record, _latest_provider_payment, _provider_payment_matches


class RazorpayAmountTests(SimpleTestCase):
    def test_amount_is_converted_to_paise_with_gateway_safe_rounding(self):
        self.assertEqual(_amount_in_paise(Decimal("2499.00")), 249900)
        self.assertEqual(_amount_in_paise(Decimal("1.005")), 101)


class RazorpayCaptureTests(SimpleTestCase):
    def _payment(self):
        payment = SimpleNamespace(
            provider_reference="order_test_123",
            amount=Decimal("20.00"),
            currency="INR",
            status="PENDING",
            provider_payment_id="",
        )
        payment.save = Mock()
        return payment

    def test_authorized_provider_payment_is_captured_before_booking_is_paid(self):
        payment = self._payment()
        client = Mock()
        client.payment.fetch.return_value = {"id": "pay_test_123", "order_id": "order_test_123", "amount": 2000, "currency": "INR", "status": "authorized"}
        client.payment.capture.return_value = {"id": "pay_test_123", "order_id": "order_test_123", "amount": 2000, "currency": "INR", "status": "captured"}

        _capture_and_record(client, payment, "pay_test_123")

        client.payment.capture.assert_called_once_with("pay_test_123", 2000, {"currency": "INR"})
        self.assertEqual(payment.status, "PAID")
        self.assertEqual(payment.provider_payment_id, "pay_test_123")

    def test_provider_payment_must_match_server_order_amount_and_currency(self):
        payment = self._payment()
        self.assertFalse(_provider_payment_matches(payment, {"order_id": "order_other", "amount": 2000, "currency": "INR"}))
        self.assertFalse(_provider_payment_matches(payment, {"order_id": "order_test_123", "amount": 1999, "currency": "INR"}))
        self.assertFalse(_provider_payment_matches(payment, {"order_id": "order_test_123", "amount": 2000, "currency": "USD"}))

    def test_reconciliation_uses_only_an_authorised_or_captured_matching_provider_payment(self):
        payment = self._payment()
        client = Mock()
        client.payment.all.return_value = {"items": [
            {"id": "pay_wrong", "order_id": "order_other", "amount": 2000, "currency": "INR", "status": "captured"},
            {"id": "pay_failed", "order_id": "order_test_123", "amount": 2000, "currency": "INR", "status": "failed"},
            {"id": "pay_authorised", "order_id": "order_test_123", "amount": 2000, "currency": "INR", "status": "authorized"},
        ]}

        self.assertEqual(_latest_provider_payment(client, payment), "pay_authorised")

