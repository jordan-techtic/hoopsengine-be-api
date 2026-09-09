"""Unit tests for organization admin support service helpers (HE-413)."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.services.org_admin_support import _validate_optional_phone


def test_validate_optional_phone_invalid_raises_400() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_optional_phone("invalid")
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "phone"


def test_validate_optional_phone_allows_none() -> None:
    _validate_optional_phone(None)
