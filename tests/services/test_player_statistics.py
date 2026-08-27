"""Unit tests for player statistics service helpers."""

from __future__ import annotations

from app.services.player_statistics import (
    _format_performance,
    _format_shooting_percentage,
    parse_player_id,
)


def test_format_shooting_percentage_with_attempts() -> None:
    assert _format_shooting_percentage(76, 100) == "76.0%"


def test_format_performance() -> None:
    assert _format_performance(18, 30) == "18/30 (60%)"


def test_parse_player_id_rejects_invalid_value() -> None:
    import pytest

    from app.core.exceptions import AppException

    with pytest.raises(AppException) as exc_info:
        parse_player_id("not-a-uuid")
    assert exc_info.value.status_code == 400
