"""Unit tests for organization admin practice plan service helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.schemas.org_admin_practice_plan import OrgAdminPracticePlanDrillInput
from app.services import org_admin_practice_plan as org_admin_practice_plan_service


def test_validate_plan_name_empty_raises() -> None:
    with pytest.raises(AppException) as exc_info:
        org_admin_practice_plan_service._validate_plan_name("   ")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_validate_org_admin_drills_empty_raises() -> None:
    with pytest.raises(AppException) as exc_info:
        org_admin_practice_plan_service._validate_org_admin_drills([])
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "drills"


def test_validate_org_admin_drills_missing_name_raises() -> None:
    with pytest.raises(AppException) as exc_info:
        org_admin_practice_plan_service._validate_org_admin_drills(
            [OrgAdminPracticePlanDrillInput(drill_name="   ", drill_description="x")]
        )
    assert exc_info.value.status_code == 400
    assert "drill_name" in exc_info.value.details[0]["field"]


def test_normalize_plan_description() -> None:
    assert org_admin_practice_plan_service._normalize_plan_description("  hello  ") == "hello"
    assert org_admin_practice_plan_service._normalize_plan_description("   ") is None
    assert org_admin_practice_plan_service._normalize_plan_description(None) is None


def test_plan_duration_label() -> None:
    assert org_admin_practice_plan_service._plan_duration_label(3) == "30 min"
    assert org_admin_practice_plan_service._plan_duration_label(0) == "10 min"
