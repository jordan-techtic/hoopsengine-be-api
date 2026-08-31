"""Integration tests for player Leaderboard API (HE-222)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import LEADERBOARD_BASE, SEEDED_PLAYER_JANE_ID

SEARCH_URL = f"{LEADERBOARD_BASE}/search"


@pytest.fixture(autouse=True)
def _player_leaderboard_seed(seed_leaderboard_data: dict) -> None:
    """Ensure leaderboard seed data is loaded for each test."""
    _ = seed_leaderboard_data


def test_get_leaderboard_200_authenticated(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.get(
        LEADERBOARD_BASE,
        headers=viewer_headers,
        params={"phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "ready"
    assert body["title"] == "Leaderboard"
    assert "avatar" in body
    assert body["phone"] == "+1-555-0100"
    assert len(body["items"]) >= 2
    first = body["items"][0]
    assert first["rank"] == 1
    assert {"name", "full_name", "shooting_percent", "attempts", "makes", "id"} <= set(first)
    assert first["full_name"] == "Jane Doe"
    assert first["shooting_percent"] == 80


def test_get_leaderboard_unauthenticated_401(client: TestClient) -> None:
    response = client.get(LEADERBOARD_BASE)
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] in {"MISSING_TOKEN", "INVALID_TOKEN"}


def test_get_leaderboard_search_valid_name_200(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.get(
        LEADERBOARD_BASE,
        headers=viewer_headers,
        params={"search_query": "Jane", "full_name": "Jane Doe"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["items"]) == 1
    assert body["items"][0]["full_name"] == "Jane Doe"
    assert body["items"][0]["id"] == str(SEEDED_PLAYER_JANE_ID)
    assert body["items"][0]["shooting_percent"] == 80


def test_get_leaderboard_search_empty_query_400(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.get(
        LEADERBOARD_BASE,
        headers=viewer_headers,
        params={"search_query": ""},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_get_leaderboard_search_no_match_404(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.get(
        LEADERBOARD_BASE,
        headers=viewer_headers,
        params={"search_query": "Nonexistent Player"},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "PLAYERS_NOT_FOUND"


def test_get_leaderboard_search_endpoint_200(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.get(
        SEARCH_URL,
        headers=viewer_headers,
        params={"search_query": "Jane", "phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["items"]) == 1
    assert body["items"][0]["full_name"] == "Jane Doe"
    assert body["items"][0]["shooting_percent"] == 80
    assert body["phone"] == "+1-555-0100"


def test_get_leaderboard_search_endpoint_empty_query_400(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.get(SEARCH_URL, headers=viewer_headers)
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_get_leaderboard_search_endpoint_no_match_404(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.get(
        SEARCH_URL,
        headers=viewer_headers,
        params={"search_query": "Nobody Here"},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "PLAYERS_NOT_FOUND"
