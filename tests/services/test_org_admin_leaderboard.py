"""Unit tests for organization admin leaderboard service helpers (HE-404)."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.services.org_admin_leaderboard import (
    _apply_ranking_direction,
    validate_optional_phone,
)


def test_validate_optional_phone_invalid_raises_400() -> None:
    with pytest.raises(AppException) as exc_info:
        validate_optional_phone("invalid")
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "phone"


def test_validate_optional_phone_allows_none() -> None:
    validate_optional_phone(None)


def test_apply_ranking_direction_bottom_reorders() -> None:
    items = [
        {"rank": 1, "full_name": "Jane", "shooting_percent": 80},
        {"rank": 2, "full_name": "Bob", "shooting_percent": 67},
    ]
    bottom = _apply_ranking_direction(items, ranking="bottom")
    assert bottom[0]["rank"] == 1
    assert bottom[0]["full_name"] == "Bob"
    assert bottom[1]["full_name"] == "Jane"
