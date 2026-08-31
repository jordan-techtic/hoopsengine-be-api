"""Unit tests for practice plan assignment service helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.schemas.practice_plan_assignment import PracticePlanAssignRequest
from app.services import practice_plan_assignment as practice_plan_assignment_service


def test_validate_assign_request_missing_fields_raises() -> None:
    with pytest.raises(AppException) as exc_info:
        practice_plan_assignment_service._validate_assign_request(
            PracticePlanAssignRequest(phone="+1-555-0100")
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"
    fields = {detail["field"] for detail in exc_info.value.details}
    assert "coach_id" in fields
    assert "plan_id" in fields
    assert "start_date" in fields


def test_normalize_frequency() -> None:
    assert practice_plan_assignment_service._normalize_frequency(" Every Tuesday ") == "Every Tuesday"
    assert practice_plan_assignment_service._normalize_frequency("   ") is None
    assert practice_plan_assignment_service._normalize_frequency(None) is None


def test_coach_display_name() -> None:
    assert practice_plan_assignment_service._coach_display_name("Taylor", "Reed") == "Taylor Reed"
    assert practice_plan_assignment_service._coach_display_name("", "") == "Coach"
