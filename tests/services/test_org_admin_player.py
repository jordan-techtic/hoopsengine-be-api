"""Unit tests for organization admin player service helpers (HE-424)."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.services.org_admin_player import (
    _build_org_admin_list_item,
    _player_status_from_row,
    _validate_player_code,
)


def test_validate_player_code_empty_raises_400() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_player_code("   ")
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "player_code"


def test_player_status_from_row_active_and_inactive() -> None:
    assert _player_status_from_row({"active": True}) == "active"
    assert _player_status_from_row({"active": False}) == "inactive"
    assert _player_status_from_row({}) == "active"


def test_build_org_admin_list_item_includes_listing_fields() -> None:
    item = _build_org_admin_list_item(
        {
            "id": "11111111-2222-3333-4444-555555555555",
            "first_name": "Ava",
            "last_name": "Morales",
            "player_code": "PC-AVA001",
            "active": True,
            "team_name": "Varsity Squad",
        }
    )
    assert item["name"] == "Ava Morales"
    assert item["code"] == "PC-AVA001"
    assert item["status"] == "active"
    assert item["team"] == "Varsity Squad"
