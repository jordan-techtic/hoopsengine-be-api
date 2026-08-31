"""Integration tests for player My Progress API (HE-214)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    PLAYER_DRILL_PERFORMANCE_BASE,
    PLAYER_MY_PROGRESS_BASE,
    PLAYER_SESSION_HISTORY_BASE,
    SEEDED_PLAYER_JANE_ID,
)


@pytest.fixture(autouse=True)
def _player_progress_seed(seed_leaderboard_data: dict) -> None:
    """Ensure leaderboard seed data and viewer-to-player link are loaded."""
    _ = seed_leaderboard_data


def test_get_my_progress_200(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.get(
        PLAYER_MY_PROGRESS_BASE,
        headers=viewer_headers,
        params={"phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "ready"
    assert body["id"] == str(SEEDED_PLAYER_JANE_ID)
    assert body["name"] == "Jane Doe"
    assert body["completed_sessions"] == 1
    assert body["total_attempts"] == 10
    assert body["makes"] == 8
    assert body["shooting_percentage"] == "80%"
    assert body["phone"] == "+1-555-0100"


def test_get_session_history_200(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.get(
        PLAYER_SESSION_HISTORY_BASE,
        headers=viewer_headers,
        params={"phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert isinstance(body["session_history"], list)
    assert len(body["session_history"]) >= 1
    first = body["session_history"][0]
    assert {"date", "drill", "attempts", "makes"} <= set(first)
    assert first["attempts"] == 10
    assert first["makes"] == 8
    assert first["drill"] == "Spot Up"


def test_get_drill_performance_200(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.get(
        PLAYER_DRILL_PERFORMANCE_BASE,
        headers=viewer_headers,
        params={"phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert isinstance(body["drill_performance"], list)
    assert len(body["drill_performance"]) >= 1
    first = body["drill_performance"][0]
    assert first["drill"] == "Spot Up"
    assert first["attempts"] == 10
    assert first["makes"] == 8
    assert first["shooting_percentage"] == "80%"


def test_progress_unauthenticated_401(client: TestClient) -> None:
    for path in (
        PLAYER_MY_PROGRESS_BASE,
        PLAYER_SESSION_HISTORY_BASE,
        PLAYER_DRILL_PERFORMANCE_BASE,
    ):
        response = client.get(path)
        assert response.status_code == 401
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] in {"MISSING_TOKEN", "INVALID_TOKEN"}


def test_progress_invalid_phone_400(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.get(
        PLAYER_MY_PROGRESS_BASE,
        headers=viewer_headers,
        params={"phone": "abc"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "phone"
