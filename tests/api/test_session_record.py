"""Integration tests for coach session mode recording API (HE-301)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import SESSIONS_BASE

MODES_URL = f"{SESSIONS_BASE}/modes"
RECORD_URL = f"{SESSIONS_BASE}/record"


@pytest.fixture(autouse=True)
def _practice_sessions_table(ensure_practice_sessions_table: None) -> None:
    """Apply session table setup for every test in this module."""


def _record_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "session_mode": "one_drill",
        "session_details": {
            "description": "Focus on a single drill and track reps, time, or performance",
        },
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


def test_get_session_modes_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.get(MODES_URL, headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["message"]
    assert body["status"] == "ready"
    assert len(body["modes"]) == 3
    modes = {item["mode"] for item in body["modes"]}
    assert modes == {"one_drill", "daily_options", "practice_plan"}


def test_get_session_mode_by_key_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.get(f"{MODES_URL}/one_drill", headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["mode"]["mode"] == "one_drill"
    assert body["mode"]["label"] == "One Drill"
    assert body["error"] is None


def test_get_session_mode_by_key_404(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.get(f"{MODES_URL}/invalid_mode", headers=coach_headers)
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "SESSION_MODE_NOT_FOUND"


def test_post_session_record_201(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.post(RECORD_URL, headers=coach_headers, json=_record_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["session_mode"] == "one_drill"
    assert body["id"]
    assert body["status"] == "in_progress"
    assert body["message"]
    assert body["error"] is None


def test_post_session_record_400_missing_session_mode_field(
    client: TestClient, coach_headers: dict[str, str]
) -> None:
    response = client.post(
        RECORD_URL,
        headers=coach_headers,
        json={"session_details": {"description": "Missing mode"}},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_post_session_record_409_duplicate_active_session(
    client: TestClient, coach_headers: dict[str, str]
) -> None:
    first = client.post(RECORD_URL, headers=coach_headers, json=_record_payload())
    assert first.status_code == 201

    second = client.post(
        RECORD_URL,
        headers=coach_headers,
        json=_record_payload(session_mode="daily_options"),
    )
    assert second.status_code == 409
    body = second.json()
    assert body["success"] is False
    assert body["error"]["code"] == "SESSION_MODE_ALREADY_RECORDED"


def test_put_session_record_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    created = client.post(RECORD_URL, headers=coach_headers, json=_record_payload())
    assert created.status_code == 201
    session_id = created.json()["id"]

    response = client.put(
        f"{RECORD_URL}/{session_id}",
        headers=coach_headers,
        json={
            "session_mode": "practice_plan",
            "session_details": {"description": "Structured multi-drill plan"},
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["session_mode"] == "practice_plan"
    assert body["message"] == "Session record updated successfully"
    assert body["error"] is None


def test_put_session_record_404(client: TestClient, coach_headers: dict[str, str]) -> None:
    missing_id = "00000000-0000-4000-8000-000000000099"
    response = client.put(
        f"{RECORD_URL}/{missing_id}",
        headers=coach_headers,
        json={"session_mode": "one_drill"},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "SESSION_NOT_FOUND"


def test_put_session_record_400_empty_body(client: TestClient, coach_headers: dict[str, str]) -> None:
    created = client.post(RECORD_URL, headers=coach_headers, json=_record_payload())
    assert created.status_code == 201
    session_id = created.json()["id"]

    response = client.put(
        f"{RECORD_URL}/{session_id}",
        headers=coach_headers,
        json={},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_get_session_modes_401_without_token(client: TestClient) -> None:
    response = client.get(MODES_URL)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"
