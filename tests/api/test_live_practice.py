"""Integration tests for Live Practice API (HE-302)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import (
    LIVE_PRACTICE_BASE,
    SEEDED_PLAYER_JANE_ID,
    sync_engine,
)


@pytest.fixture
def seed_live_practice_tables(
    ensure_practice_sessions_table: None,
    ensure_practice_plans_table: None,
) -> None:
    """Ensure drills and session_data support live practice tests."""
    with sync_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.drills (
                    id uuid PRIMARY KEY,
                    name text NOT NULL UNIQUE,
                    category text NOT NULL,
                    time_seconds integer,
                    submitted_by_org uuid,
                    approved boolean DEFAULT true,
                    created_at timestamptz DEFAULT now()
                )
                """
            )
        )
        for column, ddl in (
            ("time_seconds", "ALTER TABLE drills ADD COLUMN time_seconds integer"),
            ("submitted_by_org", "ALTER TABLE drills ADD COLUMN submitted_by_org uuid"),
            ("approved", "ALTER TABLE drills ADD COLUMN approved boolean DEFAULT true"),
        ):
            exists = connection.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'drills'
                          AND column_name = :column_name
                    )
                    """
                ),
                {"column_name": column},
            ).scalar()
            if not exists:
                connection.execute(text(ddl))

        connection.execute(text("DELETE FROM session_data"))
        connection.execute(text("DELETE FROM drills"))
        connection.execute(text("DELETE FROM practice_sessions"))
        connection.execute(
            text("UPDATE players SET active = true WHERE id = :player_id"),
            {"player_id": SEEDED_PLAYER_JANE_ID},
        )


def test_create_live_practice_drill_201(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_live_practice_tables: None,
) -> None:
    response = client.post(
        f"{LIVE_PRACTICE_BASE}/drills",
        headers=coach_headers,
        json={
            "drill_name": "3-Point Corner",
            "duration": 60,
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Drill saved successfully"
    assert body["drill_name"] == "3-Point Corner"
    assert body["duration"] == 60


def test_create_live_practice_drill_400_empty_name(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_live_practice_tables: None,
) -> None:
    response = client.post(
        f"{LIVE_PRACTICE_BASE}/drills",
        headers=coach_headers,
        json={"drill_name": "", "duration": 60},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_live_practice_drill_409_duplicate(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_live_practice_tables: None,
) -> None:
    payload = {"drill_name": "3-Point Corner", "duration": 60}
    first = client.post(f"{LIVE_PRACTICE_BASE}/drills", headers=coach_headers, json=payload)
    assert first.status_code == 201
    second = client.post(f"{LIVE_PRACTICE_BASE}/drills", headers=coach_headers, json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DRILL_ALREADY_EXISTS"


def test_create_live_practice_drill_403_non_coach(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_live_practice_tables: None,
) -> None:
    response = client.post(
        f"{LIVE_PRACTICE_BASE}/drills",
        headers=viewer_headers,
        json={"drill_name": "Baseline J", "duration": 45},
    )
    assert response.status_code == 403


def test_list_live_practice_drills_public_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_live_practice_tables: None,
) -> None:
    create = client.post(
        f"{LIVE_PRACTICE_BASE}/drills",
        headers=coach_headers,
        json={"drill_name": "Free Throw Line", "duration": 30},
    )
    assert create.status_code == 201
    response = client.get(f"{LIVE_PRACTICE_BASE}/drills")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert any(item["drill_name"] == "Free Throw Line" for item in body["drills"])


def test_timer_start_stop_status(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_live_practice_tables: None,
) -> None:
    start = client.post(
        f"{LIVE_PRACTICE_BASE}/timer/start",
        headers=coach_headers,
        json={"duration": 60, "phone": "+1-555-0100"},
    )
    assert start.status_code == 200
    assert start.json()["timer_state"] == "running"

    status = client.get(f"{LIVE_PRACTICE_BASE}/timer/status", headers=coach_headers)
    assert status.status_code == 200
    assert status.json()["timer_state"] == "running"

    stop = client.post(
        f"{LIVE_PRACTICE_BASE}/timer/stop",
        headers=coach_headers,
        json={"phone": "+1-555-0100"},
    )
    assert stop.status_code == 200
    assert stop.json()["timer_state"] == "stopped"
    assert stop.json()["elapsed_seconds"] >= 0


def test_record_and_get_player_statistics(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_live_practice_tables: None,
) -> None:
    record = client.post(
        f"{LIVE_PRACTICE_BASE}/players/{SEEDED_PLAYER_JANE_ID}/shots",
        headers=coach_headers,
        json={"shots_made": 5, "shots_attempted": 10},
    )
    assert record.status_code == 200
    body = record.json()
    assert body["success"] is True
    assert body["shots_made"] == 5
    assert body["shots_attempted"] == 10
    assert body["shooting_percent"] == 50

    stats = client.get(f"{LIVE_PRACTICE_BASE}/players/{SEEDED_PLAYER_JANE_ID}/statistics")
    assert stats.status_code == 200
    assert stats.json()["shots_made"] == 5
    assert stats.json()["shots_attempted"] == 10


def test_record_shots_400_invalid_counts(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_live_practice_tables: None,
) -> None:
    response = client.post(
        f"{LIVE_PRACTICE_BASE}/players/{SEEDED_PLAYER_JANE_ID}/shots",
        headers=coach_headers,
        json={"shots_made": 12, "shots_attempted": 5},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_and_delete_live_practice_drill(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_live_practice_tables: None,
) -> None:
    create = client.post(
        f"{LIVE_PRACTICE_BASE}/drills",
        headers=coach_headers,
        json={"drill_name": "Corner Fade", "duration": 45},
    )
    drill_id = create.json()["id"]

    update = client.put(
        f"{LIVE_PRACTICE_BASE}/drills/{drill_id}",
        headers=coach_headers,
        json={"duration": 90},
    )
    assert update.status_code == 200
    assert update.json()["duration"] == 90

    delete = client.delete(
        f"{LIVE_PRACTICE_BASE}/drills/{drill_id}",
        headers=coach_headers,
    )
    assert delete.status_code == 200
    assert delete.json()["message"] == "Drill deleted successfully"
