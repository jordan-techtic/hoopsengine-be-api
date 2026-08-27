"""Integration tests for drill catalog API (HE-309 search + HE-303 One Drill Step-2)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import (
    DRILLS_BASE,
    DRILLS_SEARCH_BASE,
    REGULAR_USER_ID,
    SEEDED_FIELD_DRILL_ID,
    SEEDED_ORG_ID,
    SEEDED_PLAYER_JANE_ID,
    sync_engine,
)


@pytest.fixture(autouse=True)
def _practice_plan_tables(ensure_practice_plans_table: None) -> None:
    """Ensure drills table is seeded for drill API tests."""


@pytest.fixture
def seed_one_drill_session(ensure_practice_sessions_table: None) -> None:
    """Seed an active one_drill session with step-1 player selected."""
    flow = {
        "one_drill_flow": {
            "step": 2,
            "selected_player_id": str(SEEDED_PLAYER_JANE_ID),
        }
    }
    with sync_engine.begin() as connection:
        connection.execute(text("DELETE FROM practice_sessions"))
        connection.execute(
            text(
                """
                INSERT INTO practice_sessions (
                    id,
                    org_id,
                    session_date,
                    session_mode,
                    session_details,
                    recorder_user_id,
                    status,
                    synced
                ) VALUES (
                    :id,
                    :org_id,
                    CURRENT_DATE,
                    'one_drill',
                    CAST(:session_details AS jsonb),
                    :recorder_user_id,
                    'in_progress',
                    true
                )
                """
            ),
            {
                "id": "00000000-0000-4000-8000-000000000060",
                "org_id": SEEDED_ORG_ID,
                "session_details": json.dumps(flow),
                "recorder_user_id": str(REGULAR_USER_ID),
            },
        )


def test_search_drills_200_matching_results(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(f"{DRILLS_SEARCH_BASE}?q=throw", headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    names = [drill["name"] for drill in body["drills"]]
    assert "Free Throw Line" in names
    assert "Free Throw Set" in names
    assert all("throw" in name.lower() for name in names)


def test_search_drills_200_warmup(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(f"{DRILLS_SEARCH_BASE}?q=Warm", headers=coach_headers)
    assert response.status_code == 200
    names = [drill["name"] for drill in response.json()["drills"]]
    assert "Warm-up Lap" in names


def test_search_drills_400_empty_query(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(f"{DRILLS_SEARCH_BASE}?q=", headers=coach_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_search_drills_400_missing_query(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(DRILLS_SEARCH_BASE, headers=coach_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_search_drills_403_for_viewer(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.get(f"{DRILLS_SEARCH_BASE}?q=warm", headers=viewer_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_list_drills_200_with_search(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(f"{DRILLS_BASE}?search=warm", headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["search"] == "warm"
    names = [drill["name"] for drill in body["drills"]]
    assert "Warm-up Lap" in names


def test_list_drills_200_full_name_alias(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(f"{DRILLS_BASE}?full_name=Corner", headers=coach_headers)
    assert response.status_code == 200
    names = [drill["name"] for drill in response.json()["drills"]]
    assert "3-Point Corner" in names


def test_list_drills_200_all_approved(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(DRILLS_BASE, headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["drills"]) >= 5
    names = {drill["name"] for drill in body["drills"]}
    assert "Inactive Spot Up" not in names


def test_get_drill_detail_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(f"{DRILLS_BASE}/{SEEDED_FIELD_DRILL_ID}", headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(SEEDED_FIELD_DRILL_ID)
    assert body["name"] == "Spot Up"
    assert body["category"] == "shooting"
    assert "image" in body


def test_get_drill_detail_404(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    missing_id = "00000000-0000-4000-8000-000000000099"
    response = client.get(f"{DRILLS_BASE}/{missing_id}", headers=coach_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DRILL_NOT_FOUND"


def test_create_drill_201(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        DRILLS_BASE,
        headers=coach_headers,
        json={
            "drill_name": "New Transition Drill",
            "drill_category": "transition",
            "duration": 45,
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["name"] == "New Transition Drill"
    assert body["category"] == "transition"
    assert body["duration"] == 45


def test_create_drill_400_empty_name(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        DRILLS_BASE,
        headers=coach_headers,
        json={"drill_name": "", "drill_category": "shooting"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_drill_409_duplicate_name(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    payload = {
        "drill_name": "Duplicate Catalog Drill",
        "drill_category": "shooting",
        "duration": 30,
    }
    first = client.post(DRILLS_BASE, headers=coach_headers, json=payload)
    assert first.status_code == 201
    second = client.post(DRILLS_BASE, headers=coach_headers, json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DRILL_ALREADY_EXISTS"


def test_update_drill_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    create = client.post(
        DRILLS_BASE,
        headers=coach_headers,
        json={
            "drill_name": "Update Me Drill",
            "drill_category": "defense",
            "duration": 20,
        },
    )
    drill_id = create.json()["id"]
    response = client.put(
        f"{DRILLS_BASE}/{drill_id}",
        headers=coach_headers,
        json={"duration": 55},
    )
    assert response.status_code == 200
    assert response.json()["duration"] == 55


def test_delete_drill_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    create = client.post(
        DRILLS_BASE,
        headers=coach_headers,
        json={
            "drill_name": "Delete Me Drill",
            "drill_category": "general",
        },
    )
    drill_id = create.json()["id"]
    response = client.delete(f"{DRILLS_BASE}/{drill_id}", headers=coach_headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Drill deleted successfully"


def test_drill_continue_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_one_drill_session: None,
) -> None:
    response = client.post(
        f"{DRILLS_BASE}/continue",
        headers=coach_headers,
        json={
            "selected_drill_id": str(SEEDED_FIELD_DRILL_ID),
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["selected_drill_id"] == str(SEEDED_FIELD_DRILL_ID)
    assert body["step"] == 3


def test_drill_continue_400_missing_drill(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_one_drill_session: None,
) -> None:
    response = client.post(
        f"{DRILLS_BASE}/continue",
        headers=coach_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 422


def test_create_drill_403_viewer(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.post(
        DRILLS_BASE,
        headers=viewer_headers,
        json={"drill_name": "Viewer Drill", "drill_category": "shooting"},
    )
    assert response.status_code == 403
