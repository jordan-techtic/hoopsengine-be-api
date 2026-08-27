"""Unit tests for player detail service helpers."""

from __future__ import annotations

from datetime import date

import pytest

from app.core.exceptions import AppException
from app.services.player import (
    _build_detail_payload,
    parse_player_date_of_birth,
)


def test_build_detail_payload_includes_frontend_fields() -> None:
    """Detail payload exposes all fields required by the Player Details screen."""
    row = {
        "id": "00000000-0000-4000-8000-000000000033",
        "first_name": "Jane",
        "last_name": "Hudson",
        "email": "jane@example.com",
        "phone": "+15551234567",
        "position": "Guard",
        "jersey_number": "23",
        "player_code": "PC-JANE001",
        "team_name": "Varsity Squad",
    }
    stats = {
        "games_played": 2,
        "goals": 10,
        "assists": 0,
        "yellow_cards": 0,
        "makes": 10,
        "attempts": 20,
        "shooting_percent": 50,
    }
    payload = _build_detail_payload(row, stats, message="Loaded")

    assert payload["success"] is True
    assert payload["title"] == "Player Details"
    assert payload["name"] == "Jane Hudson"
    assert payload["email"] == "jane@example.com"
    assert payload["phone_number"] == "+15551234567"
    assert payload["team"] == "Varsity Squad"
    assert payload["games_played"] == 2
    assert payload["goals"] == 10


def test_build_detail_payload_unknown_name_fallback() -> None:
    row = {
        "id": "00000000-0000-4000-8000-000000000033",
        "first_name": "",
        "last_name": "",
    }
    stats = {
        "games_played": 0,
        "goals": 0,
        "assists": 0,
        "yellow_cards": 0,
        "makes": 0,
        "attempts": 0,
        "shooting_percent": 0,
    }
    payload = _build_detail_payload(row, stats, message="Loaded")
    assert payload["name"] == "Unknown Player"


def test_parse_player_date_of_birth_accepts_iso_format() -> None:
    assert parse_player_date_of_birth("2000-01-01") == date(2000, 1, 1)


def test_parse_player_date_of_birth_accepts_us_format() -> None:
    assert parse_player_date_of_birth("01/15/2000") == date(2000, 1, 15)


def test_parse_player_date_of_birth_empty_400() -> None:
    with pytest.raises(AppException) as exc_info:
        parse_player_date_of_birth("   ")
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "date_of_birth"
