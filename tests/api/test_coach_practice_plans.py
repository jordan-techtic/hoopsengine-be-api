"""Integration tests for Edit Practice Plan coach endpoints (HE-309)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import COACH_PRACTICE_PLANS_BASE

VALID_CREATE_PAYLOAD = {
    "title": "Shooting Fundamentals",
    "description": "Practice plan details here.",
    "drills": [
        {"name": "Warm-up Lap"},
        {"name": "Free Throw Set"},
        {"name": "3-Point Corner"},
        {"name": "Defensive Slides"},
    ],
    "phone": "+1-555-0100",
}


@pytest.fixture(autouse=True)
def _practice_plan_tables(ensure_practice_plans_table: None) -> None:
    """Ensure practice plan tables exist for each test."""


def test_create_coach_practice_plan_201(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        COACH_PRACTICE_PLANS_BASE,
        headers=coach_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["title"] == "Shooting Fundamentals"
    assert body["name"] == "Shooting Fundamentals"
    assert body["description"] == "Practice plan details here."
    assert body["status"] == "active"
    assert body["drill_count"] == 4
    assert len(body["drills"]) == 4
    assert body["drills"][0]["name"] == "Warm-up Lap"


def test_create_coach_practice_plan_400_missing_plan_name(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    payload = {
        "drills": [{"name": "Warm-up Lap"}],
        "phone": "+1-555-0100",
    }
    response = client.post(COACH_PRACTICE_PLANS_BASE, headers=coach_headers, json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_coach_practice_plan_400_blank_plan_name(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    payload = {
        "plan_name": "   ",
        "title": "   ",
        "name": "   ",
        "drills": [{"name": "Warm-up Lap"}],
    }
    response = client.post(COACH_PRACTICE_PLANS_BASE, headers=coach_headers, json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_coach_practice_plan_409_duplicate_name(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    first = client.post(COACH_PRACTICE_PLANS_BASE, headers=coach_headers, json=VALID_CREATE_PAYLOAD)
    assert first.status_code == 201

    duplicate = client.post(COACH_PRACTICE_PLANS_BASE, headers=coach_headers, json=VALID_CREATE_PAYLOAD)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "PRACTICE_PLAN_NAME_EXISTS"


def test_get_coach_practice_plan_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    create = client.post(COACH_PRACTICE_PLANS_BASE, headers=coach_headers, json=VALID_CREATE_PAYLOAD)
    assert create.status_code == 201
    plan_id = create.json()["id"]

    response = client.get(f"{COACH_PRACTICE_PLANS_BASE}/{plan_id}", headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["id"] == plan_id
    assert body["title"] == "Shooting Fundamentals"
    assert body["description"] == "Plan Details"
    assert body["drill_count"] == 4
    assert [drill["name"] for drill in body["drills"]] == [
        "Warm-up Lap",
        "Free Throw Set",
        "3-Point Corner",
        "Defensive Slides",
    ]


def test_get_coach_practice_plan_404(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    missing_id = "00000000-0000-4000-8000-000000000099"
    response = client.get(f"{COACH_PRACTICE_PLANS_BASE}/{missing_id}", headers=coach_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRACTICE_PLAN_NOT_FOUND"


def test_update_coach_practice_plan_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    create = client.post(COACH_PRACTICE_PLANS_BASE, headers=coach_headers, json=VALID_CREATE_PAYLOAD)
    plan_id = create.json()["id"]

    update_payload = {
        "plan_name": "Updated Warmup Plan",
        "description": "Updated plan details.",
        "drills": [{"name": "Free Throw Set"}],
        "phone": "+1-555-0100",
    }
    response = client.put(
        f"{COACH_PRACTICE_PLANS_BASE}/{plan_id}",
        headers=coach_headers,
        json=update_payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["title"] == "Updated Warmup Plan"
    assert body["description"] == "Updated plan details."
    assert body["drill_count"] == 1
    assert body["drills"][0]["name"] == "Free Throw Set"


def test_update_coach_practice_plan_400_invalid_data(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    create = client.post(COACH_PRACTICE_PLANS_BASE, headers=coach_headers, json=VALID_CREATE_PAYLOAD)
    plan_id = create.json()["id"]

    response = client.put(
        f"{COACH_PRACTICE_PLANS_BASE}/{plan_id}",
        headers=coach_headers,
        json={"plan_name": "   "},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_coach_practice_plan_404(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    missing_id = "00000000-0000-4000-8000-000000000099"
    response = client.put(
        f"{COACH_PRACTICE_PLANS_BASE}/{missing_id}",
        headers=coach_headers,
        json={"plan_name": "Missing Plan"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRACTICE_PLAN_NOT_FOUND"


def test_delete_coach_practice_plan_204(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    create = client.post(COACH_PRACTICE_PLANS_BASE, headers=coach_headers, json=VALID_CREATE_PAYLOAD)
    plan_id = create.json()["id"]

    delete = client.delete(f"{COACH_PRACTICE_PLANS_BASE}/{plan_id}", headers=coach_headers)
    assert delete.status_code == 204
    assert delete.content == b""

    get_response = client.get(f"{COACH_PRACTICE_PLANS_BASE}/{plan_id}", headers=coach_headers)
    assert get_response.status_code == 404


def test_delete_coach_practice_plan_404(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    missing_id = "00000000-0000-4000-8000-000000000099"
    response = client.delete(f"{COACH_PRACTICE_PLANS_BASE}/{missing_id}", headers=coach_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRACTICE_PLAN_NOT_FOUND"


def test_coach_practice_plan_mutations_403_for_viewer(
    client: TestClient,
    coach_headers: dict[str, str],
    viewer_headers: dict[str, str],
) -> None:
    create = client.post(COACH_PRACTICE_PLANS_BASE, headers=coach_headers, json=VALID_CREATE_PAYLOAD)
    plan_id = create.json()["id"]

    update = client.put(
        f"{COACH_PRACTICE_PLANS_BASE}/{plan_id}",
        headers=viewer_headers,
        json={"plan_name": "Blocked"},
    )
    assert update.status_code == 403
    assert update.json()["error"]["code"] == "FORBIDDEN"

    delete = client.delete(f"{COACH_PRACTICE_PLANS_BASE}/{plan_id}", headers=viewer_headers)
    assert delete.status_code == 403
    assert delete.json()["error"]["code"] == "FORBIDDEN"
