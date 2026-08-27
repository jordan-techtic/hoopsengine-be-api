"""Unit tests for live practice helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.schemas.live_practice import LivePracticePlayerStatInput
from app.services.live_practice import (
    TIMER_RUNNING,
    TIMER_STOPPED,
    _compute_elapsed_seconds,
    _validate_drill_name,
    _validate_player_stats,
)


def test_validate_drill_name_empty_400() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_drill_name("  ")
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "drill_name"


def test_validate_player_stats_invalid_shots_400() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_player_stats(
            [
                LivePracticePlayerStatInput(
                    player_id="00000000-0000-4000-8000-000000000033",
                    shots_made=10,
                    shots_attempted=5,
                )
            ]
        )
    assert exc_info.value.status_code == 400
    assert "player_stats[0].shots_made" in exc_info.value.details[0]["field"]


def test_compute_elapsed_seconds_running() -> None:
    from datetime import datetime, timezone

    now = datetime(2026, 1, 1, 12, 0, 30, tzinfo=timezone.utc)
    timer = {
        "state": TIMER_RUNNING,
        "elapsed_seconds": 10,
        "started_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
    }
    assert _compute_elapsed_seconds(timer, now=now) == 40


def test_compute_elapsed_seconds_stopped() -> None:
    timer = {"state": TIMER_STOPPED, "elapsed_seconds": 25}
    assert _compute_elapsed_seconds(timer) == 25
