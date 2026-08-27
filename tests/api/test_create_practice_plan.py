"""Integration tests for Create Practice Plan API (HE-308)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import DRILLS_SEARCH_BASE, PRACTICE_PLANS_BASE

CREATE_SCREEN_PAYLOAD = {
    "plan_name": "Morning Shooting Routine",
    "selected_drills": ["Spot Up", "Free Throw Line"],
    "full_name": "Jane Doe",
    "phone": "+1-555-0100",
}


@pytest.fixture(autouse=True)
def _practice_plan_tables(ensure_practice_plans_table: None) -> None:
    """Ensure practice plan tables exist for each test."""


def test_create_practice_plan_create_screen_201(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        PRACTICE_PLANS_BASE,
        headers=coach_headers,
        json=CREATE_SCREEN_PAYLOAD,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["id"]
    assert body["name"] == "Morning Shooting Routine"
    assert body["status"] == "active"
    assert body["description"]
    assert body["drill_count"] == 2
    assert [drill["name"] for drill in body["drills"]] == ["Spot Up", "Free Throw Line"]


def test_create_practice_plan_create_screen_400_empty_plan_name(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    payload = {
        **CREATE_SCREEN_PAYLOAD,
        "plan_name": "   ",
        "full_name": "   ",
    }
    response = client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_practice_plan_create_screen_409_duplicate_name(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    first = client.post(
        PRACTICE_PLANS_BASE,
        headers=coach_headers,
        json=CREATE_SCREEN_PAYLOAD,
    )
    assert first.status_code == 201

    duplicate = client.post(
        PRACTICE_PLANS_BASE,
        headers=coach_headers,
        json=CREATE_SCREEN_PAYLOAD,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "PRACTICE_PLAN_NAME_EXISTS"


def test_create_practice_plan_accepts_full_name_as_plan_name(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    payload = {
        "full_name": "Evening Defense Plan",
        "selected_drills": ["Defensive Slides"],
        "phone": "+1-555-0100",
    }
    response = client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json=payload)
    assert response.status_code == 201
    assert response.json()["name"] == "Evening Defense Plan"


def test_search_drills_returns_only_active_drills(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(f"{DRILLS_SEARCH_BASE}?q=spot", headers=coach_headers)
    assert response.status_code == 200
    names = [drill["name"] for drill in response.json()["drills"]]
    assert "Spot Up" in names
    assert "Inactive Spot Up" not in names
