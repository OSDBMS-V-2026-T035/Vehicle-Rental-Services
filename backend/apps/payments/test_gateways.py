from django.test import SimpleTestCase, override_settings

from .gateways import RazorpayGateway, get_payment_gateway, register_payment_gateway


class PaymentGatewayRegistryTests(SimpleTestCase):
    def test_default_provider_resolves_to_lazy_razorpay_adapter(self):
        self.assertIsInstance(get_payment_gateway(), RazorpayGateway)

    @override_settings(PAYMENT_GATEWAY="RAZORPAY")
    def test_configured_provider_is_used(self):
        self.assertIsInstance(get_payment_gateway(), RazorpayGateway)

    def test_unknown_provider_fails_closed(self):
        with self.assertRaisesMessage(ValueError, "Unsupported payment provider: UNKNOWN"):
            get_payment_gateway("unknown")

    def test_registry_supports_an_independent_adapter(self):
        class TestGateway:
            pass

        register_payment_gateway("TEST_ONLY", TestGateway)
        try:
            self.assertIsInstance(get_payment_gateway("test_only"), TestGateway)
        finally:
            from . import gateways
            gateways._GATEWAYS.pop("TEST_ONLY", None)
