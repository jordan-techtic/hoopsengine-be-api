"""Unit tests for Super Admin dashboard analytics helpers (JAW-9600)."""

from app.models.enums import BillingFrequency
from app.services.dashboard import list_price_dollars, monthly_list_price_cents


def test_monthly_list_price_cents_monthly_unchanged() -> None:
    """Monthly plan list prices are already monthly cents."""
    assert monthly_list_price_cents(4900, BillingFrequency.MONTHLY.value) == 4900


def test_monthly_list_price_cents_yearly_divides_by_12() -> None:
    """A $1200/year plan contributes $100/month (120000 cents / 12)."""
    assert monthly_list_price_cents(120000, BillingFrequency.YEARLY.value) == 10000


def test_list_price_dollars_converts_cents() -> None:
    """Cent totals become whole-dollar integers for the dashboard field."""
    assert list_price_dollars(4900) == 49
    assert list_price_dollars(0) == 0
    assert list_price_dollars(10000) == 100


def test_monthly_then_dollars_yearly_plan() -> None:
    """Yearly $1200 list price contributes 100 dollars of estimated MRR."""
    monthly_cents = monthly_list_price_cents(120000, BillingFrequency.YEARLY.value)
    assert list_price_dollars(monthly_cents) == 100


def test_monthly_list_price_cents_unknown_frequency_treated_as_monthly() -> None:
    """Non-yearly frequencies keep the list price as monthly cents."""
    assert monthly_list_price_cents(2500, "weekly") == 2500


def test_list_price_dollars_truncates_fractional_dollars() -> None:
    """int(cents_to_decimal) drops cents below a whole dollar."""
    assert list_price_dollars(199) == 1
    assert list_price_dollars(99) == 0
