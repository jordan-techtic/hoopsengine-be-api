"""Integration tests for coach practice plan CRUD API (HE-310)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    PRACTICE_PLANS_BASE,
    SEEDED_FIELD_DRILL_ID,
    SEEDED_FT_DRILL_ID,
    coach_headers,
)

VALID_CREATE_PAYLOAD = {
    "name": "Shooting Fundamentals",
    "drills": [
        {
            "id": str(SEEDED_FIELD_DRILL_ID),
            "name": "Spot Up",
            "type": "shooting",
        }
    ],
    "phone": "+1-555-0100",
}


@pytest.fixture(autouse=True)
def _practice_plan_tables(ensure_practice_plans_table: None) -> None:
    """Ensure practice plan tables exist for each test."""


def test_create_practice_plan_201(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json=VALID_CREATE_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["name"] == "Shooting Fundamentals"
    assert body["status"] == "active"
    assert body["drill_count"] == 1
    assert body["created_by_name"] == "Regular Coach"
    assert len(body["drills"]) == 1
    assert body["drills"][0]["type"] == "shooting"


def test_create_practice_plan_400_missing_name(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    payload = {**VALID_CREATE_PAYLOAD, "name": "   "}
    response = client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_practice_plan_422_missing_required_fields(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json={"phone": "+1-555-0100"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_practice_plan_409_duplicate_name(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    first = client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json=VALID_CREATE_PAYLOAD)
    assert first.status_code == 201

    duplicate = client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json=VALID_CREATE_PAYLOAD)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "PRACTICE_PLAN_NAME_EXISTS"


def test_list_active_practice_plans_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    create = client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json=VALID_CREATE_PAYLOAD)
    assert create.status_code == 201

    inactive_payload = {
        "name": "Inactive Plan",
        "drills": [
            {
                "id": str(SEEDED_FT_DRILL_ID),
                "name": "Free Throw Line",
                "type": "free_throw",
            }
        ],
    }
    inactive = client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json=inactive_payload)
    plan_id = inactive.json()["id"]
    delete = client.delete(f"{PRACTICE_PLANS_BASE}/{plan_id}", headers=coach_headers)
    assert delete.status_code == 204

    response = client.get(PRACTICE_PLANS_BASE, headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "ready"
    assert len(body["plans"]) == 1
    assert body["plans"][0]["name"] == "Shooting Fundamentals"
    assert body["plans"][0]["drill_count"] == 1
    assert body["plans"][0]["created_by_name"] == "Regular Coach"


def test_update_practice_plan_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    create = client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json=VALID_CREATE_PAYLOAD)
    plan_id = create.json()["id"]

    update_payload = {
        "name": "Updated Warmup Plan",
        "drills": [
            {
                "id": str(SEEDED_FT_DRILL_ID),
                "name": "Free Throw Line",
                "type": "free_throw",
            }
        ],
        "phone": "+1-555-0100",
    }
    response = client.put(
        f"{PRACTICE_PLANS_BASE}/{plan_id}",
        headers=coach_headers,
        json=update_payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["name"] == "Updated Warmup Plan"
    assert body["drill_count"] == 1
    assert body["drills"][0]["type"] == "free_throw"


def test_update_practice_plan_400_invalid_data(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    create = client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json=VALID_CREATE_PAYLOAD)
    plan_id = create.json()["id"]

    response = client.put(
        f"{PRACTICE_PLANS_BASE}/{plan_id}",
        headers=coach_headers,
        json={"name": "   "},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_practice_plan_404(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    missing_id = "00000000-0000-4000-8000-000000000099"
    response = client.put(
        f"{PRACTICE_PLANS_BASE}/{missing_id}",
        headers=coach_headers,
        json={"name": "Missing Plan"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRACTICE_PLAN_NOT_FOUND"


def test_delete_practice_plan_204(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    create = client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json=VALID_CREATE_PAYLOAD)
    plan_id = create.json()["id"]

    delete = client.delete(f"{PRACTICE_PLANS_BASE}/{plan_id}", headers=coach_headers)
    assert delete.status_code == 204
    assert delete.content == b""

    listing = client.get(PRACTICE_PLANS_BASE, headers=coach_headers)
    assert listing.status_code == 200
    assert listing.json()["plans"] == []


def test_delete_practice_plan_404(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    missing_id = "00000000-0000-4000-8000-000000000099"
    response = client.delete(f"{PRACTICE_PLANS_BASE}/{missing_id}", headers=coach_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRACTICE_PLAN_NOT_FOUND"


def test_practice_plan_endpoints_401_without_auth(client: TestClient) -> None:
    response = client.get(PRACTICE_PLANS_BASE)
    assert response.status_code == 401
