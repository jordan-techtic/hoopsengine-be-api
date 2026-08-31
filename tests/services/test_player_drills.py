"""Unit tests for player drill timer helpers (HE-455)."""

from __future__ import annotations

from uuid import UUID

from app.services import player_drills as player_drills_service


def test_format_mm_ss_zero_pads() -> None:
    assert player_drills_service._format_mm_ss(65) == "01:05"
    assert player_drills_service._format_mm_ss(600) == "10:00"


def test_compute_time_remaining_countdown() -> None:
    timer = {
        "state": "stopped",
        "elapsed_seconds": 120,
        "duration_seconds": 600,
    }
    assert player_drills_service._time_remaining(timer, duration_seconds=600) == "08:00"


def test_merge_player_workout_details_preserves_drills() -> None:
    existing = {
        "player_workout": {
            "drills": [{"drill_id": "11111111-2222-3333-4444-555555555555", "name": "Test"}],
            "timer": {"state": "stopped", "elapsed_seconds": 0},
        }
    }
    merged = player_drills_service._merge_player_workout_details(
        existing,
        current_drill_id=UUID("11111111-2222-3333-4444-555555555555"),
    )
    assert merged["player_workout"]["drills"][0]["name"] == "Test"
    assert merged["player_workout"]["current_drill_id"] == "11111111-2222-3333-4444-555555555555"


def test_workout_current_matches() -> None:
    details = {"player_workout": {"current_drill_id": "11111111-2222-3333-4444-555555555555"}}
    assert player_drills_service.workout_current_matches(
        details,
        UUID("11111111-2222-3333-4444-555555555555"),
    )
    assert not player_drills_service.workout_current_matches(
        details,
        UUID("22222222-2222-3333-4444-555555555555"),
    )


def test_response_status_reset() -> None:
    timer = {"state": "stopped", "elapsed_seconds": 0}
    assert player_drills_service._response_status(timer, reset=True) == "reset"


def test_compute_progress() -> None:
    assert player_drills_service._compute_progress(90, 600) == 15
    assert player_drills_service._compute_progress(600, 600) == 100
    assert player_drills_service._compute_progress(0, 0) == 0


def test_parse_timer_mm_ss() -> None:
    assert player_drills_service._parse_timer_mm_ss("01:30") == 90
    assert player_drills_service._parse_timer_mm_ss("00:00") == 0


def test_playback_status_paused() -> None:
    timer = {"state": "paused", "elapsed_seconds": 30}
    assert player_drills_service._playback_status(timer) == "paused"
