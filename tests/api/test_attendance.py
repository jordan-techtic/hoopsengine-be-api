"""Integration tests for coach Attendance API (HE-307)."""

from __future__ import annotations

import json
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import (
    ATTENDANCE_BASE,
    ATTENDANCE_SEARCH_BASE,
    REGULAR_EMAIL,
    SEEDED_ORG_ID,
    SEEDED_PLAYER_BOB_ID,
    SEEDED_PLAYER_JANE_ID,
    sync_engine,
)

ATTENDANCE_PLAYER_ALEX_ID = UUID("00000000-0000-4000-8000-000000000050")
ATTENDANCE_PLAYER_DAVID_ID = UUID("00000000-0000-4000-8000-000000000051")
ATTENDANCE_SESSION_ID = UUID("00000000-0000-4000-8000-000000000060")


@pytest.fixture
def seed_attendance_players(
    ensure_practice_sessions_table: None,
    ensure_practice_plans_table: None,
) -> None:
    """Seed active players with jersey numbers for attendance tests."""
    with sync_engine.begin() as connection:
        for column, ddl in (
            ("jersey_number", "ALTER TABLE players ADD COLUMN jersey_number text"),
            ("active", "ALTER TABLE players ADD COLUMN active boolean DEFAULT true"),
        ):
            exists = connection.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'players'
                          AND column_name = :column_name
                    )
                    """
                ),
                {"column_name": column},
            ).scalar()
            if not exists:
                connection.execute(text(ddl))

        connection.execute(
            text(
                """
                INSERT INTO players (
                    id, org_id, first_name, last_name, player_code,
                    jersey_number, active
                ) VALUES
                    (:alex_id, :org_id, 'Alex', 'Martinez', 'PC-ALEX001', '12', true),
                    (:david_id, :org_id, 'David', 'Park', 'PC-DAVID01', '15', true)
                ON CONFLICT (id) DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    jersey_number = EXCLUDED.jersey_number,
                    active = true
                """
            ),
            {
                "alex_id": ATTENDANCE_PLAYER_ALEX_ID,
                "david_id": ATTENDANCE_PLAYER_DAVID_ID,
                "org_id": SEEDED_ORG_ID,
            },
        )
        connection.execute(
            text(
                """
                UPDATE players
                SET jersey_number = '23', active = true
                WHERE id = :jane_id
                """
            ),
            {"jane_id": SEEDED_PLAYER_JANE_ID},
        )
        connection.execute(
            text(
                """
                UPDATE players
                SET jersey_number = '7', active = true
                WHERE id = :bob_id
                """
            ),
            {"bob_id": SEEDED_PLAYER_BOB_ID},
        )
        connection.execute(
            text("DELETE FROM practice_sessions WHERE recorder_user_id IS NOT NULL")
        )


def test_search_attendance_players_by_name_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_attendance_players: None,
) -> None:
    response = client.get(
        ATTENDANCE_SEARCH_BASE,
        headers=coach_headers,
        params={"full_name": "Alex"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["players"]) >= 1
    assert body["players"][0]["name"] == "Alex Martinez"
    assert body["players"][0]["jersey_number"] == "12"
    assert body["players"][0]["status"] in {"present", "absent"}


def test_search_attendance_players_by_jersey_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_attendance_players: None,
) -> None:
    response = client.get(
        ATTENDANCE_SEARCH_BASE,
        headers=coach_headers,
        params={"search_query": "15"},
    )
    assert response.status_code == 200
    body = response.json()
    names = [player["name"] for player in body["players"]]
    assert "David Park" in names


def test_search_attendance_players_empty_400(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_attendance_players: None,
) -> None:
    response = client.get(ATTENDANCE_SEARCH_BASE, headers=coach_headers, params={"full_name": ""})
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_attendance_summary_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_attendance_players: None,
) -> None:
    with sync_engine.begin() as connection:
        coach_user_id = connection.execute(
            text("SELECT id FROM users WHERE email = :email LIMIT 1"),
            {"email": REGULAR_EMAIL},
        ).scalar()
        connection.execute(
            text(
                """
                INSERT INTO practice_sessions (
                    id, org_id, session_date, session_details, recorder_user_id,
                    recorder_type, status, synced
                ) VALUES (
                    :id, :org_id, CURRENT_DATE,
                    CAST(:details AS jsonb),
                    :coach_user_id,
                    'coach', 'attendance', true
                )
                """
            ),
            {
                "id": ATTENDANCE_SESSION_ID,
                "org_id": SEEDED_ORG_ID,
                "coach_user_id": coach_user_id,
                "details": json.dumps(
                    {
                        "attendance": {
                            "players": {
                                str(ATTENDANCE_PLAYER_ALEX_ID): "present",
                                str(ATTENDANCE_PLAYER_DAVID_ID): "present",
                                str(SEEDED_PLAYER_JANE_ID): "absent",
                            }
                        }
                    }
                ),
            },
        )

    response = client.get(f"{ATTENDANCE_BASE}/summary", headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["attendance_summary"]["present_count"] >= 2
    assert body["attendance_summary"]["total_count"] >= 3
    assert body["description"] == "Only present players will appear in recording"
    statuses = {player["name"]: player["status"] for player in body["players"]}
    assert statuses["Alex Martinez"] == "present"
    assert all(player["status"] in {"present", "absent"} for player in body["players"])


def test_attendance_summary_only_active_players(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_attendance_players: None,
) -> None:
    with sync_engine.begin() as connection:
        connection.execute(
            text("UPDATE players SET active = false WHERE id = :player_id"),
            {"player_id": ATTENDANCE_PLAYER_DAVID_ID},
        )

    response = client.get(f"{ATTENDANCE_BASE}/summary", headers=coach_headers)
    assert response.status_code == 200
    names = [player["name"] for player in response.json()["players"]]
    assert "David Park" not in names


def test_start_attendance_practice_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_attendance_players: None,
) -> None:
    response = client.post(
        f"{ATTENDANCE_BASE}/start-practice",
        headers=coach_headers,
        json={
            "present_player_ids": [
                str(ATTENDANCE_PLAYER_ALEX_ID),
                str(SEEDED_PLAYER_JANE_ID),
            ],
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Practice started successfully"
    assert body["status"] == "in_progress"
    assert body["attendance_summary"]["present_count"] == 2
    assert body["session_id"] == body["id"]

    with sync_engine.begin() as connection:
        row = connection.execute(
            text(
                """
                SELECT status
                FROM practice_sessions
                WHERE id = :session_id
                """
            ),
            {"session_id": body["session_id"]},
        ).mappings().first()
    assert row is not None
    assert row["status"] == "in_progress"


def test_start_attendance_practice_403_non_coach(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_attendance_players: None,
) -> None:
    response = client.post(
        f"{ATTENDANCE_BASE}/start-practice",
        headers=viewer_headers,
        json={"present_player_ids": [str(ATTENDANCE_PLAYER_ALEX_ID)]},
    )
    assert response.status_code == 403
