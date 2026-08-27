"""Unit tests for practice plan service validation helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.exceptions import AppException
from app.schemas.practice_plan import PracticePlanDrillInput
from app.services.practice_plan import _validate_drills, _validate_plan_name


def test_validate_plan_name_rejects_empty() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_plan_name("   ")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_validate_plan_name_returns_trimmed_value() -> None:
    assert _validate_plan_name("  Warmup  ") == "Warmup"


def test_validate_drills_requires_at_least_one() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_drills([])
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_validate_drills_rejects_blank_fields() -> None:
    drills = [
        PracticePlanDrillInput(id=uuid4(), name=" ", type="shooting"),
    ]
    with pytest.raises(AppException) as exc_info:
        _validate_drills(drills)
    assert exc_info.value.status_code == 400
    details = exc_info.value.details
    assert isinstance(details, list)
    assert any(item["field"] == "drills[0].name" for item in details)
