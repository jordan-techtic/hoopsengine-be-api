"""Integration tests for Practice Plans screen API (HE-306/HE-251)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import PRACTICE_PLANS_BASE, SEEDED_FIELD_DRILL_ID

VALID_CREATE_PAYLOAD = {
    "name": "Warm-Up Routine",
    "drills": [
        {
            "id": str(SEEDED_FIELD_DRILL_ID),
            "name": "Spot Up",
            "type": "shooting",
        }
    ],
    "phone": "+1-555-0100",
}

ROSTER_SEARCH_BASE = f"{PRACTICE_PLANS_BASE}/search"


@pytest.fixture(autouse=True)
def _practice_plan_tables(ensure_practice_plans_table: None) -> None:
    """Ensure practice plan and roster tables exist for each test."""


def test_list_practice_plans_200_with_card_fields(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    create = client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json=VALID_CREATE_PAYLOAD)
    assert create.status_code == 201

    response = client.get(PRACTICE_PLANS_BASE, headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "ready"
    assert body["description"]
    assert len(body["plans"]) == 1

    plan = body["plans"][0]
    assert plan["id"]
    assert plan["name"] == "Warm-Up Routine"
    assert plan["status"] == "active"
    assert plan["drill_count"] == 1
    assert plan["duration"] == "10 min"
    assert plan["category"] == "Skills"
    assert plan["created_by_name"] == "Regular Coach"


def test_list_practice_plans_200_for_viewer(
    client: TestClient,
    coach_headers: dict[str, str],
    viewer_headers: dict[str, str],
) -> None:
    create = client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json=VALID_CREATE_PAYLOAD)
    assert create.status_code == 201

    response = client.get(PRACTICE_PLANS_BASE, headers=viewer_headers)
    assert response.status_code == 200
    assert len(response.json()["plans"]) == 1


def test_search_roster_by_name_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(f"{ROSTER_SEARCH_BASE}?q=Jane", headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    names = [player["name"] for player in body["players"]]
    assert "Jane Hudson" in names


def test_search_roster_by_jersey_number_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(f"{ROSTER_SEARCH_BASE}?q=7", headers=coach_headers)
    assert response.status_code == 200
    players = response.json()["players"]
    assert len(players) == 1
    assert players[0]["name"] == "Bob Smith"
    assert players[0]["jersey_number"] == "7"


def test_search_roster_excludes_inactive_players(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(f"{ROSTER_SEARCH_BASE}?q=Inactive", headers=coach_headers)
    assert response.status_code == 200
    assert response.json()["players"] == []


def test_search_roster_400_empty_query(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(f"{ROSTER_SEARCH_BASE}?q=", headers=coach_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_search_roster_403_without_auth(client: TestClient) -> None:
    response = client.get(f"{ROSTER_SEARCH_BASE}?q=Jane")
    assert response.status_code == 403
