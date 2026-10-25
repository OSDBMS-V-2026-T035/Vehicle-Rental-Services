"""Financial snapshotting for RideHub bookings.

Commission is calculated on the rental fare, which currently has no separate
tax or refundable-deposit fields.  Tax is therefore stored as zero instead of
inventing a GST rate.  A later tax implementation can supply a non-zero tax
amount without changing the commission base.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

MONEY = Decimal("0.01")


def money(value):
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def snapshot_booking_financials(booking):
    """Freeze a booking's terms exactly once; safe for repeated callbacks."""
    from apps.adminpanel.models import CommissionConfiguration

    if booking.financial_confirmed_at:
        return booking
    config = CommissionConfiguration.objects.order_by("-updated_at", "-id").first()
    if config is None:
        # No silent charge: a missing policy means a recorded 0% rate.
        rate = Decimal("0.00")
    else:
        rate = Decimal(config.commission_rate)
    base = money(booking.total_amount)
    commission = money(base * rate / Decimal("100"))
    booking.commissionable_base = base
    booking.tax_amount = Decimal("0.00")
    booking.commission_rate = rate
    booking.platform_commission = commission
    booking.shopkeeper_net_earnings = money(base - commission)
    booking.financial_confirmed_at = timezone.now()
    booking.save(update_fields=[
        "commissionable_base", "tax_amount", "commission_rate", "platform_commission",
        "shopkeeper_net_earnings", "financial_calculation_version", "financial_confirmed_at", "updated_at",
    ])
    return booking


def reverse_booking_commission(booking):
    """Mark the already frozen commission reversed; never delete history."""
    if booking.financial_confirmed_at and not booking.commission_reversed_at:
        booking.commission_reversed_at = timezone.now()
        booking.save(update_fields=["commission_reversed_at", "updated_at"])
    return booking
