"""Unit tests for One Drill Step-3 session helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.services.one_drill_session import _validate_metric_counts


def test_validate_metric_counts_accepts_valid_values() -> None:
    _validate_metric_counts(makes=5, attempts=10, free_throws_makes=2, free_throws_attempts=3)


def test_validate_metric_counts_rejects_makes_over_attempts() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_metric_counts(makes=11, attempts=10, free_throws_makes=0, free_throws_attempts=0)
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_validate_metric_counts_rejects_free_throw_makes_over_attempts() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_metric_counts(makes=1, attempts=2, free_throws_makes=4, free_throws_attempts=3)
    assert exc_info.value.status_code == 400
