"""Integration tests for coach offline sync APIs (HE-319)."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import (
    COACH_CLEAR_CACHE_BASE,
    COACH_SYNC_BASE,
    COACH_SYNC_PREFERENCES_BASE,
    REGULAR_USER_ID,
    SEEDED_FIELD_DRILL_ID,
    SEEDED_ORG_ID,
    SEEDED_PLAYER_ID,
    sync_engine,
    viewer_headers,
)


@pytest.fixture(autouse=True)
def _sync_tables(ensure_practice_sessions_table: None) -> None:
    with sync_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.drills (
                    id uuid PRIMARY KEY,
                    name text NOT NULL,
                    category text NOT NULL
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
        connection.execute(text("DELETE FROM session_data"))
        connection.execute(text("DELETE FROM practice_sessions"))
        connection.execute(
            text(
                """
                INSERT INTO drills (id, name, category)
                VALUES (:id, 'Defense Drill', 'defense')
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                """
            ),
            {"id": SEEDED_FIELD_DRILL_ID},
        )
        connection.execute(
            text(
                """
                INSERT INTO practice_sessions (
                    id, org_id, session_date, session_mode, recorder_user_id,
                    recorder_type, status, synced, created_at
                ) VALUES (
                    :id, :org_id, :session_date, 'one_drill', :recorder_user_id,
                    'coach', 'in_progress', false, NOW()
                )
                """
            ),
            {
                "id": "00000000-0000-4000-8000-000000000080",
                "org_id": SEEDED_ORG_ID,
                "session_date": date(2026, 7, 28),
                "recorder_user_id": REGULAR_USER_ID,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO session_data (
                    id, session_id, org_id, player_id, drill_id, makes, attempts,
                    session_date, synced
                ) VALUES (
                    :id, :session_id, :org_id, :player_id, :drill_id, 5, 10,
                    :session_date, false
                )
                """
            ),
            {
                "id": "00000000-0000-4000-8000-000000000081",
                "session_id": "00000000-0000-4000-8000-000000000080",
                "org_id": SEEDED_ORG_ID,
                "player_id": SEEDED_PLAYER_ID,
                "drill_id": SEEDED_FIELD_DRILL_ID,
                "session_date": date(2026, 7, 28),
            },
        )


def test_trigger_sync_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        COACH_SYNC_BASE,
        headers=coach_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["id"] == str(REGULAR_USER_ID)


def test_trigger_sync_409_when_in_progress(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    from sqlalchemy.orm import Session

    from app.models.user import User
    from app.services.coach_sync import _set_sync_preferences

    with Session(sync_engine) as session:
        user = session.get(User, REGULAR_USER_ID)
        assert user is not None
        _set_sync_preferences(user, sync_in_progress=True)
        session.commit()

    response = client.post(COACH_SYNC_BASE, headers=coach_headers, json={})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SYNC_IN_PROGRESS"


def test_update_sync_preferences_400_invalid_frequency(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.put(
        COACH_SYNC_PREFERENCES_BASE,
        headers=coach_headers,
        json={"sync_frequency": "often"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_sync_preferences_400_empty_frequency(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.put(
        COACH_SYNC_PREFERENCES_BASE,
        headers=coach_headers,
        json={"sync_frequency": "   "},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_and_update_sync_preferences_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    get_response = client.get(
        f"{COACH_SYNC_PREFERENCES_BASE}?phone=%2B1-555-0100",
        headers=coach_headers,
    )
    assert get_response.status_code == 200
    get_body = get_response.json()
    assert get_body["auto_sync"] is True
    assert get_body["sync_frequency"] == "Every 15 minutes"
    assert get_body["id"] == str(REGULAR_USER_ID)

    put_response = client.put(
        COACH_SYNC_PREFERENCES_BASE,
        headers=coach_headers,
        json={"auto_sync": False, "sync_frequency": "Every 30 minutes"},
    )
    assert put_response.status_code == 200
    body = put_response.json()
    assert body["auto_sync"] is False
    assert body["sync_frequency"] == "Every 30 minutes"


def test_clear_cache_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        COACH_CLEAR_CACHE_BASE,
        headers=coach_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_sync_endpoints_403_for_viewer(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.get(COACH_SYNC_PREFERENCES_BASE, headers=viewer_headers)
    assert response.status_code == 403
