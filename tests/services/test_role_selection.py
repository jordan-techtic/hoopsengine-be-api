"""Unit tests for role selection service helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.models.enums import UserRole
from app.services.role_selection import (
    ALLOWED_SELECTION_VALUES,
    build_roles_catalog_response,
    list_available_roles,
    normalize_selection_role,
)


def test_normalize_organiser_maps_to_org_admin() -> None:
    assert normalize_selection_role("Organiser") == UserRole.ORG_ADMIN.value
    assert normalize_selection_role("organizer") == UserRole.ORG_ADMIN.value


def test_normalize_coach_and_player() -> None:
    assert normalize_selection_role("Coach") == UserRole.COACH.value
    assert normalize_selection_role("Player") == UserRole.PLAYER.value


def test_validate_selected_role_empty_raises_400() -> None:
    with pytest.raises(AppException) as exc_info:
        normalize_selection_role("   ")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert exc_info.value.details[0]["field"] == "selected_role"


def test_validate_selected_role_referee_raises_400() -> None:
    with pytest.raises(AppException) as exc_info:
        normalize_selection_role("Referee")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_validate_selected_role_super_admin_raises_409() -> None:
    with pytest.raises(AppException) as exc_info:
        normalize_selection_role("Super Admin")
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "ROLE_NOT_ALLOWED"


def test_validate_selected_role_unknown_raises_409() -> None:
    with pytest.raises(AppException) as exc_info:
        normalize_selection_role("Janitor")
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "ROLE_NOT_ALLOWED"


def test_list_available_roles_contains_three_options() -> None:
    roles = list_available_roles()
    assert len(roles) == 3
    values = {role.value for role in roles}
    assert values == set(ALLOWED_SELECTION_VALUES)


def test_build_roles_catalog_response_envelope() -> None:
    payload = build_roles_catalog_response()
    assert payload["success"] is True
    assert payload["title"] == "Select Your Role"
    assert payload["error"] is None
    assert len(payload["roles"]) == 3
