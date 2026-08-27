"""Integration tests for One Drill Step-1 coach drill flow API (HE-324)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import COACH_DRILLS_BASE, SEEDED_PLAYER_BOB_ID, SEEDED_PLAYER_JANE_ID

SEARCH_URL = f"{COACH_DRILLS_BASE}/search"
SELECT_URL = f"{COACH_DRILLS_BASE}/select_player"
CONTINUE_URL = f"{COACH_DRILLS_BASE}/continue"


@pytest.fixture(autouse=True)
def _tables(ensure_practice_plans_table: None, ensure_practice_sessions_table: None) -> None:
    """Ensure players and practice session tables exist."""


def test_search_players_200_valid_query(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        SEARCH_URL,
        headers=coach_headers,
        json={"search_query": "Jane", "full_name": "Jane Hudson", "phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["search_query"] == "Jane"
    assert len(body["players"]) >= 1
    names = [player["name"] for player in body["players"]]
    assert "Jane Hudson" in names


def test_search_players_400_empty_query(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        SEARCH_URL,
        headers=coach_headers,
        json={"search_query": "", "full_name": "", "phone": "+1-555-0100"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_search_players_200_jersey_number(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        SEARCH_URL,
        headers=coach_headers,
        json={"search_query": "23", "phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert any(player.get("jersey_number") == "23" for player in body["players"])


def test_select_player_200_valid_id(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        SELECT_URL,
        headers=coach_headers,
        json={
            "selected_player_id": str(SEEDED_PLAYER_JANE_ID),
            "full_name": "Jane Hudson",
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["selected_player_id"] == str(SEEDED_PLAYER_JANE_ID)
    assert body["link"] == f"{COACH_DRILLS_BASE}/continue"
    assert body["error"] is None


def test_select_player_409_missing_player(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    missing_id = "00000000-0000-4000-8000-000000000099"
    response = client.post(
        SELECT_URL,
        headers=coach_headers,
        json={"selected_player_id": missing_id, "phone": "+1-555-0100"},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "PLAYER_NOT_FOUND"


def test_continue_200_after_selection(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    selected = client.post(
        SELECT_URL,
        headers=coach_headers,
        json={"selected_player_id": str(SEEDED_PLAYER_JANE_ID), "phone": "+1-555-0100"},
    )
    assert selected.status_code == 200

    response = client.post(CONTINUE_URL, headers=coach_headers, json={"phone": "+1-555-0100"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["step"] == 2
    assert body["error"] is None
    assert body["message"]


def test_continue_400_no_player_selected(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(CONTINUE_URL, headers=coach_headers, json={"phone": "+1-555-0100"})
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_search_players_403_viewer(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.post(
        SEARCH_URL,
        headers=viewer_headers,
        json={"search_query": "Jane"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_select_player_409_inactive_player(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    inactive_id = "00000000-0000-4000-8000-000000000035"
    response = client.post(
        SELECT_URL,
        headers=coach_headers,
        json={"selected_player_id": inactive_id},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PLAYER_NOT_FOUND"


def test_select_player_200_bob(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        SELECT_URL,
        headers=coach_headers,
        json={"selected_player_id": str(SEEDED_PLAYER_BOB_ID)},
    )
    assert response.status_code == 200
    assert response.json()["selected_player_id"] == str(SEEDED_PLAYER_BOB_ID)
