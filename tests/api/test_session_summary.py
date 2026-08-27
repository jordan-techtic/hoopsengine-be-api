"""Integration tests for coach session summary API (HE-305)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import SESSIONS_BASE

RECORD_URL = f"{SESSIONS_BASE}/record"


@pytest.fixture(autouse=True)
def _session_tables(ensure_practice_sessions_table: None) -> None:
    """Ensure practice session tables exist for summary tests."""


def test_get_session_summary_200_with_player_stats(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_session_summary_data: dict,
) -> None:
    session_id = seed_session_summary_data["session_id"]
    response = client.get(f"{SESSIONS_BASE}/{session_id}", headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["session_id"] == str(session_id)
    assert body["id"] == str(session_id)
    assert body["error"] is None
    assert body["session_time"] == "9:41"
    assert len(body["player_stats"]) == 1
    stats = body["player_stats"][0]
    assert stats["player_name"] == "Charlie Hudson"
    assert stats["attempts"] == 10
    assert stats["makes"] == 6
    assert stats["shooting_percent"] == 60
    assert stats["free_throw_attempts"] == 5
    assert stats["free_throw_makes"] == 4
    assert stats["free_throw_percent"] == 80


def test_get_session_summary_404_invalid_id(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_session_summary_data: dict,
) -> None:
    missing_id = "00000000-0000-4000-8000-000000000099"
    response = client.get(f"{SESSIONS_BASE}/{missing_id}", headers=coach_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_get_session_summary_403_other_coach(
    client: TestClient,
    seed_session_summary_data: dict,
) -> None:
    session_id = seed_session_summary_data["session_id"]
    response = client.get(
        f"{SESSIONS_BASE}/{session_id}",
        headers=seed_session_summary_data["other_coach_headers"],
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SESSION_ACCESS_FORBIDDEN"


def test_next_drill_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_session_summary_data: dict,
) -> None:
    session_id = seed_session_summary_data["session_id"]
    response = client.post(
        f"{SESSIONS_BASE}/{session_id}/next-drill",
        headers=coach_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["current_drill_index"] == 1
    assert body["status"] == "in_progress"
    assert body["error"] is None


def test_end_practice_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_session_summary_data: dict,
) -> None:
    session_id = seed_session_summary_data["session_id"]
    response = client.post(
        f"{SESSIONS_BASE}/{session_id}/end-practice",
        headers=coach_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "Session Complete! Nice work, coach"
    assert body["message"] == "Practice session ended successfully"
    assert body["error"] is None
    assert len(body["player_stats"]) == 1
