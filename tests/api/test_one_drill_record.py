"""Integration tests for One Drill session recording API (HE-300)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import DRILLS_BASE, REGULAR_USER_ID, SEEDED_FIELD_DRILL_ID, SESSIONS_BASE

RECORD_URL = f"{SESSIONS_BASE}/record"


@pytest.fixture(autouse=True)
def _session_tables(
    ensure_practice_sessions_table: None,
    ensure_practice_plans_table: None,
) -> None:
    """Ensure drills and practice_sessions tables are ready."""


def _one_drill_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "session_mode": "one_drill",
        "drill_id": str(SEEDED_FIELD_DRILL_ID),
        "user_id": str(REGULAR_USER_ID),
        "session_data": {
            "reps": 10,
            "time": "00:30:00",
            "performance": "good",
        },
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


def test_record_one_drill_session_201(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(RECORD_URL, headers=coach_headers, json=_one_drill_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["session_mode"] == "one_drill"
    assert body["title"] == "One Drill"
    assert body["id"]
    assert body["message"]
    assert body["status"] == "in_progress"
    flow = body["session_details"]["one_drill_flow"]
    assert flow["selected_drill_id"] == str(SEEDED_FIELD_DRILL_ID)
    assert flow["session_data"]["reps"] == 10
    assert flow["session_data"]["time"] == "00:30:00"
    assert flow["session_data"]["performance"] == "good"


def test_record_one_drill_session_400_missing_drill_id(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    payload = _one_drill_payload()
    del payload["drill_id"]
    response = client.post(RECORD_URL, headers=coach_headers, json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(detail["field"] == "drill_id" for detail in body["error"]["details"])


def test_record_one_drill_session_400_missing_session_data(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    payload = _one_drill_payload()
    del payload["session_data"]
    response = client.post(RECORD_URL, headers=coach_headers, json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(detail["field"] == "session_data" for detail in body["error"]["details"])


def test_record_one_drill_session_409_duplicate_drill(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    first = client.post(RECORD_URL, headers=coach_headers, json=_one_drill_payload())
    assert first.status_code == 201

    second = client.post(RECORD_URL, headers=coach_headers, json=_one_drill_payload())
    assert second.status_code == 409
    body = second.json()
    assert body["success"] is False
    assert body["error"]["code"] == "SESSION_ALREADY_RECORDED"


def test_list_drills_200_for_selection(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(DRILLS_BASE, headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["message"]
    assert body["status"] == "ready"
    assert len(body["drills"]) >= 1
    drill = body["drills"][0]
    assert drill["id"]
    assert drill["name"]
    assert drill["category"]
    assert "duration" in drill


def test_record_one_drill_session_422_invalid_session_mode(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        RECORD_URL,
        headers=coach_headers,
        json=_one_drill_payload(session_mode="invalid_mode"),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
