"""Unit tests for player Start screen helpers (HE-229)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.schemas.player_start import PlayerStartDrillItem
from app.services import player_start as player_start_service
from app.services.player_identity import PlayerContext


def test_seconds_to_minutes_rounds_up_to_one() -> None:
    assert player_start_service._seconds_to_minutes(600) == 10
    assert player_start_service._seconds_to_minutes(0) == 1


@pytest.mark.asyncio
async def test_resolve_and_serialize_workout_drills_stores_seconds() -> None:
    items = [
        PlayerStartDrillItem(name="Warm-up Lap", duration=10),
        PlayerStartDrillItem(name="3-Point Corner", duration=8),
    ]
    player_ctx = PlayerContext(
        player_id=UUID("00000000-0000-4000-8000-000000000039"),
        org_id=UUID("00000000-0000-4000-8000-000000000010"),
        subteam_id=UUID("00000000-0000-4000-8000-000000000040"),
        row={},
    )
    assigned_rows = [
        {
            "id": "00000000-0000-4000-8000-000000000041",
            "name": "Warm-up Lap",
            "time_seconds": 600,
        },
        {
            "id": "00000000-0000-4000-8000-000000000043",
            "name": "3-Point Corner",
            "time_seconds": 480,
        },
    ]
    db = AsyncMock()
    with patch.object(
        player_start_service,
        "_fetch_assigned_drill_rows",
        new=AsyncMock(return_value=assigned_rows),
    ):
        serialized, first_drill_id = await player_start_service._resolve_and_serialize_workout_drills(
            db,
            player_ctx,
            items,
        )

    assert serialized[0]["duration_seconds"] == 600
    assert serialized[1]["duration_seconds"] == 480
    assert serialized[0]["drill_id"] == "00000000-0000-4000-8000-000000000041"
    assert serialized[1]["drill_id"] == "00000000-0000-4000-8000-000000000043"
    assert first_drill_id == UUID("00000000-0000-4000-8000-000000000041")


def test_drills_from_session_row() -> None:
    session_row = {
        "session_details": {
            "player_workout": {
                "drills": [
                    {"name": "Warm-up Lap", "duration_seconds": 600},
                    {"name": "3-Point Corner", "duration": 8},
                ]
            }
        }
    }
    drills = player_start_service._drills_from_session_row(session_row)
    assert len(drills) == 2
    assert drills[0].name == "Warm-up Lap"
    assert drills[0].duration == 10
    assert drills[1].duration == 8
