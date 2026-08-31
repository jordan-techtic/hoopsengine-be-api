"""Unit tests for organization admin team service helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.services import org_admin_team as org_admin_team_service


def test_validate_team_name_empty_raises() -> None:
    with pytest.raises(AppException) as exc_info:
        org_admin_team_service._validate_team_name("   ")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert exc_info.value.details[0]["field"] == "team_name"


def test_validate_team_code_empty_raises() -> None:
    with pytest.raises(AppException) as exc_info:
        org_admin_team_service._validate_team_code("")
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "team_code"


def test_normalize_team_description() -> None:
    assert org_admin_team_service._normalize_team_description("  hello  ") == "hello"
    assert org_admin_team_service._normalize_team_description("   ") is None
    assert org_admin_team_service._normalize_team_description(None) is None


def test_normalize_age_group() -> None:
    assert org_admin_team_service._normalize_age_group(" 16-18 ") == "16-18"
    assert org_admin_team_service._normalize_age_group("   ") is None
    assert org_admin_team_service._normalize_age_group(None) is None
