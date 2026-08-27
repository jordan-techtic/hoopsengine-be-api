"""Unit tests for drill idea validation helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.schemas.drill_idea import DrillIdeaCreateRequest
from app.services.drill_idea import _resolve_drill_name, _validate_difficulty_level


def test_resolve_drill_name_from_drill_name() -> None:
    payload = DrillIdeaCreateRequest(
        drill_name="Fast Break",
        category="Shooting",
        difficulty_level="Beginner",
        instructions="Run the drill.",
    )
    assert _resolve_drill_name(payload) == "Fast Break"


def test_resolve_drill_name_from_full_name_alias() -> None:
    payload = DrillIdeaCreateRequest(
        category="Shooting",
        difficulty_level="Beginner",
        instructions="Run the drill.",
        full_name="Alias Drill Name",
    )
    assert _resolve_drill_name(payload) == "Alias Drill Name"


def test_resolve_drill_name_raises_when_missing() -> None:
    payload = DrillIdeaCreateRequest(
        drill_name="",
        category="Shooting",
        difficulty_level="Beginner",
        instructions="Run the drill.",
        full_name="",
    )
    with pytest.raises(AppException) as exc_info:
        _resolve_drill_name(payload)
    assert exc_info.value.status_code == 400


def test_validate_difficulty_level_accepts_intermediate() -> None:
    assert _validate_difficulty_level("intermediate") == "Intermediate"


def test_validate_difficulty_level_rejects_invalid() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_difficulty_level("Pro")
    assert exc_info.value.status_code == 400
