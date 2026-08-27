"""Integration tests for coach leaderboard API (HE-314)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import LEADERBOARD_BASE

SEARCH_URL = f"{LEADERBOARD_BASE}/search"
FILTER_URL = f"{LEADERBOARD_BASE}/filter"


@pytest.fixture(autouse=True)
def _leaderboard_tables(seed_leaderboard_data: dict) -> None:
    """Ensure leaderboard seed data is loaded for each test."""


def test_get_leaderboard_200_public(
    client: TestClient,
    seed_leaderboard_data: dict,
) -> None:
    response = client.get(LEADERBOARD_BASE)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "ready"
    assert "title" in body
    assert "profile" in body
    assert "phone" in body
    assert len(body["items"]) >= 3
    first = body["items"][0]
    assert first["rank"] == 1
    assert "full_name" in first
    assert "name" in first
    assert "shooting_percent" in first
    assert "attempts" in first
    assert "makes" in first
    assert "id" in first


def test_post_search_leaderboard_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.post(
        SEARCH_URL,
        headers=coach_headers,
        json={
            "search_query": "Jane",
            "full_name": "Jane Doe",
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["items"]) == 1
    assert body["items"][0]["full_name"] == "Jane Doe"
    assert body["items"][0]["name"] == "Jane Doe"
    assert body["items"][0]["shooting_percent"] == 80


def test_get_search_leaderboard_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.get(
        SEARCH_URL,
        headers=coach_headers,
        params={"search_query": "Charlie"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["items"]) == 1
    assert body["items"][0]["full_name"] == "Charlie Hudson"


def test_get_search_leaderboard_400_empty_query(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.get(SEARCH_URL, headers=coach_headers)
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_post_search_leaderboard_400_empty_query(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.post(
        SEARCH_URL,
        headers=coach_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_filter_leaderboard_200_shooting_percent(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.get(
        FILTER_URL,
        headers=coach_headers,
        params={"filter_metric": "shooting_percent"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["items"][0]["full_name"] == "Jane Doe"
    assert body["items"][0]["rank"] == 1


def test_get_filter_leaderboard_200_attempts(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.get(
        FILTER_URL,
        headers=coach_headers,
        params={"filter_metric": "attempts"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["full_name"] == "Bob Smith"
    assert body["items"][0]["attempts"] == 30


def test_search_leaderboard_401_without_auth(
    client: TestClient,
    seed_leaderboard_data: dict,
) -> None:
    response = client.post(SEARCH_URL, json={"search_query": "Jane"})
    assert response.status_code == 401
