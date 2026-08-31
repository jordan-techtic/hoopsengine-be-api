"""Unit tests for player progress service helpers."""

from __future__ import annotations

from datetime import datetime

from app.services.player_progress import (
    format_iso_date,
    format_progress_shooting_percentage,
)


def test_format_progress_shooting_percentage_with_attempts() -> None:
    assert format_progress_shooting_percentage(61, 100) == "61%"


def test_format_progress_shooting_percentage_zero_attempts() -> None:
    assert format_progress_shooting_percentage(0, 0) == "0%"


def test_format_iso_date() -> None:
    assert format_iso_date(datetime(2026, 8, 4, 15, 30)) == "2026-08-04"
