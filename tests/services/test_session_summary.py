"""Unit tests for session summary helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.session_summary import (
    compute_shooting_percent,
    format_session_time,
)


def test_compute_shooting_percent() -> None:
    assert compute_shooting_percent(6, 10) == 60
    assert compute_shooting_percent(0, 0) == 0


def test_format_session_time() -> None:
    started = datetime(2026, 8, 27, 8, 0, 0, tzinfo=timezone.utc)
    ended = datetime(2026, 8, 27, 8, 9, 41, tzinfo=timezone.utc)
    assert format_session_time(started, ended) == "9:41"


def test_aggregate_free_throw_stats_pattern() -> None:
    assert compute_shooting_percent(4, 5) == 80
