"""Customer-facing booking-change and cancellation terms."""

from decimal import Decimal, ROUND_HALF_UP


MONEY = Decimal("0.01")
CANCELLATION_TIERS = (
    {"minimum_days": 5, "percent": 100, "label": "5 or more calendar days before pickup"},
    {"minimum_days": 2, "percent": 80, "label": "2–4 calendar days before pickup"},
    {"minimum_days": 1, "percent": 50, "label": "1 calendar day before pickup"},
    {"minimum_days": 0, "percent": 0, "label": "On the pickup date"},
)


def cancellation_refund_percent(pickup_date, today):
    """Return the promised refund percentage based on whole calendar days."""
    days_before_pickup = (pickup_date - today).days
    for tier in CANCELLATION_TIERS:
        if days_before_pickup >= tier["minimum_days"]:
            return tier["percent"]
    return 0


def refund_amount(amount, percent):
    """Calculate a money-safe refund for one captured payment source."""
    return (Decimal(amount) * Decimal(percent) / Decimal("100")).quantize(
        MONEY, rounding=ROUND_HALF_UP,
    )


def cancellation_policy_payload(pickup_date, today, refundable_base):
    percent = cancellation_refund_percent(pickup_date, today)
    return {
        "percent": percent,
        "estimated_refund": str(refund_amount(refundable_base, percent)),
        "tiers": [dict(tier) for tier in CANCELLATION_TIERS],
    }
