"""Integration tests for One Drill Step-3 session management API (HE-304)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import (
    SEEDED_FIELD_DRILL_ID,
    SEEDED_FT_DRILL_ID,
    SEEDED_ORG_ID,
    SEEDED_PLAYER_ID,
    SESSIONS_BASE,
    sync_engine,
)


@pytest.fixture(autouse=True)
def _session_tables(ensure_practice_sessions_table: None) -> None:
    """Ensure session and related client tables exist."""


@pytest.fixture
def seed_step3_support_data(seeded_users: dict) -> None:
    """Seed players and drills used by Step-3 session tests."""
    with sync_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.players (
                    id uuid PRIMARY KEY,
                    org_id uuid,
                    first_name text NOT NULL,
                    last_name text NOT NULL,
                    player_code text UNIQUE,
                    active boolean DEFAULT true,
                    created_at timestamptz DEFAULT now()
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.drills (
                    id uuid PRIMARY KEY,
                    name text NOT NULL,
                    category text NOT NULL,
                    created_at timestamptz DEFAULT now()
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.session_data (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id uuid,
                    org_id uuid NOT NULL,
                    player_id uuid NOT NULL,
                    drill_id uuid,
                    makes integer NOT NULL DEFAULT 0,
                    attempts integer NOT NULL DEFAULT 0,
                    session_date date NOT NULL DEFAULT CURRENT_DATE,
                    recorded_at timestamptz DEFAULT now(),
                    synced boolean DEFAULT true
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO players (id, org_id, first_name, last_name, player_code)
                VALUES (:id, :org_id, 'Charlie', 'Hudson', 'PC-CHARLIE1')
                ON CONFLICT (id) DO UPDATE SET first_name = EXCLUDED.first_name
                """
            ),
            {"id": SEEDED_PLAYER_ID, "org_id": SEEDED_ORG_ID},
        )
        connection.execute(
            text(
                """
                INSERT INTO drills (id, name, category)
                VALUES
                    (:field_id, '3-Point Shooting', 'shooting'),
                    (:ft_id, 'Free Throw Line', 'free_throw')
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    category = EXCLUDED.category
                """
            ),
            {"field_id": SEEDED_FIELD_DRILL_ID, "ft_id": SEEDED_FT_DRILL_ID},
        )


def _create_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "player": "Charlie Hudson",
        "drill": "3-Point Shooting",
        "makes": 5,
        "attempts": 10,
        "free_throws_makes": 2,
        "free_throws_attempts": 3,
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


def test_create_one_drill_session_201(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_step3_support_data: None,
) -> None:
    response = client.post(SESSIONS_BASE, headers=coach_headers, json=_create_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["player"] == "Charlie Hudson"
    assert body["drill"] == "3-Point Shooting"
    assert body["makes"] == 5
    assert body["attempts"] == 10
    assert body["free_throws_makes"] == 2
    assert body["free_throws_attempts"] == 3
    assert body["id"]
    assert body["message"]
    assert body["status"]


def test_create_one_drill_session_400_missing_required_fields(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_step3_support_data: None,
) -> None:
    response = client.post(
        SESSIONS_BASE,
        headers=coach_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_create_one_drill_session_400_empty_player(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_step3_support_data: None,
) -> None:
    response = client.post(
        SESSIONS_BASE,
        headers=coach_headers,
        json=_create_payload(player=""),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_update_one_drill_session_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_step3_support_data: None,
) -> None:
    created = client.post(SESSIONS_BASE, headers=coach_headers, json=_create_payload())
    assert created.status_code == 201
    session_id = created.json()["id"]

    response = client.put(
        f"{SESSIONS_BASE}/{session_id}",
        headers=coach_headers,
        json={
            "makes": 7,
            "attempts": 12,
            "free_throws_makes": 3,
            "free_throws_attempts": 4,
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["makes"] == 7
    assert body["attempts"] == 12
    assert body["free_throws_makes"] == 3
    assert body["free_throws_attempts"] == 4
    assert body["error"] is None


def test_get_one_drill_session_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_step3_support_data: None,
) -> None:
    created = client.post(SESSIONS_BASE, headers=coach_headers, json=_create_payload())
    assert created.status_code == 201
    session_id = created.json()["id"]

    response = client.get(f"{SESSIONS_BASE}/{session_id}", headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["id"] == session_id
    assert body["player"] == "Charlie Hudson"
    assert body["drill"] == "3-Point Shooting"
    assert body["makes"] == 5
    assert body["attempts"] == 10
    assert body["error"] is None


def test_list_sessions_summary_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_step3_support_data: None,
) -> None:
    created = client.post(SESSIONS_BASE, headers=coach_headers, json=_create_payload())
    assert created.status_code == 201

    response = client.get(f"{SESSIONS_BASE}/summary", headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert len(body["sessions"]) >= 1
    item = body["sessions"][0]
    assert item["player"] == "Charlie Hudson"
    assert item["drill"] == "3-Point Shooting"
    assert item["makes"] == 5
    assert item["attempts"] == 10


def test_get_one_drill_session_404(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_step3_support_data: None,
) -> None:
    missing_id = "00000000-0000-4000-8000-000000000099"
    response = client.get(f"{SESSIONS_BASE}/{missing_id}", headers=coach_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"
