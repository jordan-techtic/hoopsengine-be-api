"""Integration tests for player Home Screen API (HE-221)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import PLAYER_HOME_BASE, SEEDED_PLAYER_JANE_ID


@pytest.fixture(autouse=True)
def _player_home_seed(seed_leaderboard_data: dict) -> None:
    """Ensure leaderboard seed data and viewer-to-player link are loaded."""
    _ = seed_leaderboard_data


def test_get_player_home_200(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.get(
        PLAYER_HOME_BASE,
        headers=viewer_headers,
        params={"phone": "+1-555-0100", "company": "Acme Realty"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "ready"
    assert body["title"] == "Home"
    assert body["id"] == str(SEEDED_PLAYER_JANE_ID)
    assert body["name"] == "Jane Doe"
    assert body["user_name"] == "Jane Doe"
    assert body["team_name"] == "Seeded Hoops Club"
    assert body["jersey_number"] == "23"
    assert body["total_sessions"] == 1
    assert body["total_attempts"] == 10
    assert isinstance(body["recent_sessions"], list)
    assert len(body["recent_sessions"]) >= 1
    session = body["recent_sessions"][0]
    assert {"session_name", "attempts", "fg_percentage"} <= set(session)
    assert session["attempts"] == 10
    assert session["fg_percentage"] == "80%"
    assert isinstance(body["motivational_card"], str)
    assert body["motivational_card"]
    assert body["phone"] == "+1-555-0100"
    assert body["company"] == "Acme Realty"
    assert body["profile"]["user_name"] == "Jane Doe"
    assert body["profile"]["team_name"] == "Seeded Hoops Club"


def test_get_player_home_unauthenticated_401(client: TestClient) -> None:
    response = client.get(PLAYER_HOME_BASE)
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] in {"MISSING_TOKEN", "INVALID_TOKEN"}


def test_get_player_home_player_not_found_404(
    client: TestClient,
    unverified_player_headers: dict[str, str],
) -> None:
    response = client.get(PLAYER_HOME_BASE, headers=unverified_player_headers)
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "PLAYER_NOT_FOUND"


def test_get_player_home_invalid_phone_400(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.get(
        PLAYER_HOME_BASE,
        headers=viewer_headers,
        params={"phone": "abc"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "phone"
