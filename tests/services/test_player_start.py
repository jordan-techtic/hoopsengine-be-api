"""Unit tests for player Start screen helpers (HE-229)."""

from __future__ import annotations

from app.schemas.player_start import PlayerStartDrillItem
from app.services import player_start as player_start_service


def test_seconds_to_minutes_rounds_up_to_one() -> None:
    assert player_start_service._seconds_to_minutes(600) == 10
    assert player_start_service._seconds_to_minutes(0) == 1


def test_serialize_workout_drills_stores_seconds() -> None:
    items = [
        PlayerStartDrillItem(name="Catch & Shoot From Wing", duration=10),
        PlayerStartDrillItem(name="Cone Slasher Layup Finishing", duration=8),
    ]
    serialized = player_start_service._serialize_workout_drills(items)
    assert serialized[0]["duration_seconds"] == 600
    assert serialized[1]["duration_seconds"] == 480


def test_drills_from_session_row() -> None:
    session_row = {
        "session_details": {
            "player_workout": {
                "drills": [
                    {"name": "Catch & Shoot From Wing", "duration_seconds": 600},
                    {"name": "Cone Slasher Layup Finishing", "duration": 8},
                ]
            }
        }
    }
    drills = player_start_service._drills_from_session_row(session_row)
    assert len(drills) == 2
    assert drills[0].name == "Catch & Shoot From Wing"
    assert drills[0].duration == 10
    assert drills[1].duration == 8
