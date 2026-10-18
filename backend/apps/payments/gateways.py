"""Provider registry for payment integrations (OSA-style ports and adapters).

Business views depend on the small gateway contract below rather than importing a
provider SDK. Provider adapters own credentials and provider-specific calls.
"""

from dataclasses import dataclass
from typing import Protocol

from django.conf import settings


class PaymentGateway(Protocol):
    """Operations RideHub requires from a payment provider."""

    name: str

    def create_order(self, data): ...
    def fetch_order(self, order_id): ...
    def fetch_payment(self, payment_id): ...
    def capture_payment(self, payment_id, amount, options): ...
    def list_payments(self, order_id, count=100): ...
    def verify_payment_signature(self, data): ...
    def verify_webhook_signature(self, body, signature, secret): ...
    def refund(self, payment_id, data): ...


@dataclass
class RazorpayGateway:
    """Lazy Razorpay adapter. Importing the app never requires SDK credentials."""

    name = "RAZORPAY"

    @property
    def client(self):
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise RuntimeError("Razorpay is not configured.")
        import razorpay
        return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    def create_order(self, data):
        return self.client.order.create(data=data)

    def fetch_order(self, order_id):
        return self.client.order.fetch(order_id)

    def fetch_payment(self, payment_id):
        return self.client.payment.fetch(payment_id)

    def capture_payment(self, payment_id, amount, options):
        return self.client.payment.capture(payment_id, amount, options)

    def list_payments(self, order_id, count=100):
        return self.client.payment.all({"order_id": order_id, "count": count})

    def verify_payment_signature(self, data):
        return self.client.utility.verify_payment_signature(data)

    def verify_webhook_signature(self, body, signature, secret):
        return self.client.utility.verify_webhook_signature(body, signature, secret)

    def refund(self, payment_id, data):
        return self.client.payment.refund(payment_id, data)


_GATEWAYS = {"RAZORPAY": RazorpayGateway}


def register_payment_gateway(name, gateway_factory):
    """Register an adapter class/factory under a stable provider key."""
    normalized = str(name or "").strip().upper()
    if not normalized or not callable(gateway_factory):
        raise ValueError("A provider name and callable gateway factory are required.")
    _GATEWAYS[normalized] = gateway_factory


def get_payment_gateway(name=None) -> PaymentGateway:
    """Resolve configured/default provider or fail closed for unknown providers."""
    normalized = str(name or getattr(settings, "PAYMENT_GATEWAY", "RAZORPAY") or "RAZORPAY").strip().upper()
    factory = _GATEWAYS.get(normalized)
    if factory is None:
        raise ValueError(f"Unsupported payment provider: {normalized}")
    return factory()
