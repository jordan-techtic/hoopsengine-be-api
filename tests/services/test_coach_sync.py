"""Unit tests for coach sync service helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.services.coach_sync import parse_sync_frequency_minutes


def test_parse_sync_frequency_minutes_from_label() -> None:
    assert parse_sync_frequency_minutes("Every 15 minutes") == 15


def test_parse_sync_frequency_minutes_from_numeric_string() -> None:
    assert parse_sync_frequency_minutes("30") == 30


def test_parse_sync_frequency_minutes_rejects_non_numeric() -> None:
    with pytest.raises(AppException) as exc_info:
        parse_sync_frequency_minutes("often")
    assert exc_info.value.status_code == 400


def test_parse_sync_frequency_minutes_rejects_empty() -> None:
    with pytest.raises(AppException) as exc_info:
        parse_sync_frequency_minutes("   ")
    assert exc_info.value.status_code == 400
