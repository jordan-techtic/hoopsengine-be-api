"""Unit tests for leaderboard service helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.models.enums import LeaderboardFilterMetric
from app.services.leaderboard import _rank_items, resolve_search_text


def test_resolve_search_text_prefers_search_query() -> None:
    assert resolve_search_text(search_query="Jane", full_name="Other") == "Jane"


def test_resolve_search_text_uses_full_name_when_query_missing() -> None:
    assert resolve_search_text(search_query=None, full_name="Jane Doe") == "Jane Doe"


def test_resolve_search_text_raises_when_empty() -> None:
    with pytest.raises(AppException) as exc_info:
        resolve_search_text(search_query=None, full_name=None)
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert exc_info.value.status_code == 400


def test_rank_items_by_shooting_percent() -> None:
    items = [
        {
            "id": "1",
            "name": "Bob",
            "full_name": "Bob",
            "shooting_percent": 67,
            "attempts": 30,
            "makes": 20,
        },
        {
            "id": "2",
            "name": "Jane",
            "full_name": "Jane",
            "shooting_percent": 80,
            "attempts": 10,
            "makes": 8,
        },
    ]
    ranked = _rank_items(items, LeaderboardFilterMetric.SHOOTING_PERCENT)
    assert ranked[0]["full_name"] == "Jane"
    assert ranked[0]["rank"] == 1
    assert ranked[1]["rank"] == 2


def test_rank_items_by_attempts() -> None:
    items = [
        {
            "id": "1",
            "name": "Bob",
            "full_name": "Bob",
            "shooting_percent": 67,
            "attempts": 30,
            "makes": 20,
        },
        {
            "id": "2",
            "name": "Jane",
            "full_name": "Jane",
            "shooting_percent": 80,
            "attempts": 10,
            "makes": 8,
        },
    ]
    ranked = _rank_items(items, LeaderboardFilterMetric.ATTEMPTS)
    assert ranked[0]["full_name"] == "Bob"
    assert ranked[0]["rank"] == 1
