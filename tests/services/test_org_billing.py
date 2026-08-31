"""Unit tests for organization admin billing service helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.schemas.org_billing import PaymentMethodUpdateRequest
from app.services.org_billing import validate_payment_method_payload


def test_validate_payment_method_payload_success() -> None:
    payload = PaymentMethodUpdateRequest(
        card_number="4242424242424242",
        expiry_date="12/28",
        cvv="123",
    )
    card_number, exp_month, exp_year, cvv = validate_payment_method_payload(payload)
    assert card_number == "4242424242424242"
    assert exp_month == 12
    assert exp_year == 2028
    assert cvv == "123"


def test_validate_payment_method_payload_invalid_luhn_400() -> None:
    payload = PaymentMethodUpdateRequest(
        card_number="4242424242424243",
        expiry_date="12/28",
        cvv="123",
    )
    with pytest.raises(AppException) as exc_info:
        validate_payment_method_payload(payload)
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "card_number"


def test_validate_payment_method_payload_invalid_expiry_400() -> None:
    payload = PaymentMethodUpdateRequest(
        card_number="4242424242424242",
        expiry_date="13/28",
        cvv="123",
    )
    with pytest.raises(AppException) as exc_info:
        validate_payment_method_payload(payload)
    assert exc_info.value.details[0]["field"] == "expiry_date"
