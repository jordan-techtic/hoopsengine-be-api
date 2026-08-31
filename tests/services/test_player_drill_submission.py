"""Unit tests for player drill submission service."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.schemas.player_drill_submission import PlayerDrillSubmissionCreateRequest
from app.services import player_drill_submission as player_drill_submission_service


def test_resolve_drill_name_from_full_name_alias() -> None:
    payload = PlayerDrillSubmissionCreateRequest(
        category="Shooting",
        difficulty_level="Beginner",
        description="Setup and cues.",
        full_name="Alias Drill Name",
    )
    assert player_drill_submission_service._resolve_drill_name(payload) == "Alias Drill Name"


def test_resolve_drill_name_missing_raises_400() -> None:
    payload = PlayerDrillSubmissionCreateRequest(
        category="Shooting",
        difficulty_level="Beginner",
        description="Setup and cues.",
        drill_name="",
        full_name="",
    )
    with pytest.raises(AppException) as exc_info:
        player_drill_submission_service._resolve_drill_name(payload)
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"
