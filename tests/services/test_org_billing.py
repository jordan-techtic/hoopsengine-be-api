"""Unit tests for organization admin billing service helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.services.org_billing import validate_stripe_payment_method_id


def test_validate_stripe_payment_method_id_success() -> None:
    assert validate_stripe_payment_method_id("pm_test_4242") == "pm_test_4242"


def test_validate_stripe_payment_method_id_empty_400() -> None:
    with pytest.raises(AppException) as exc_info:
        validate_stripe_payment_method_id("")
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "stripe_payment_method_id"


def test_validate_stripe_payment_method_id_invalid_prefix_400() -> None:
    with pytest.raises(AppException) as exc_info:
        validate_stripe_payment_method_id("card_test_123")
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "stripe_payment_method_id"
