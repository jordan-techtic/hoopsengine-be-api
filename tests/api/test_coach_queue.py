"""Integration tests for coach sync queue API (HE-329)."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import (
    COACH_QUEUE_BASE,
    REGULAR_USER_ID,
    SEEDED_FIELD_DRILL_ID,
    SEEDED_ORG_ID,
    SEEDED_PLAYER_ID,
    sync_engine,
)


@pytest.fixture(autouse=True)
def _queue_tables(ensure_practice_sessions_table: None) -> None:
    """Ensure queue-related client tables exist."""
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
                "id": "00000000-0000-4000-8000-000000000070",
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
                "id": "00000000-0000-4000-8000-000000000071",
                "session_id": "00000000-0000-4000-8000-000000000070",
                "org_id": SEEDED_ORG_ID,
                "player_id": SEEDED_PLAYER_ID,
                "drill_id": SEEDED_FIELD_DRILL_ID,
                "session_date": date(2026, 7, 28),
            },
        )


def test_get_queue_200_with_pending_items(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(f"{COACH_QUEUE_BASE}?phone=%2B1-555-0100", headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["pending_count"] >= 2
    assert "Pending Sync" in body["title"]
    assert body["name"]
    assert len(body["items"]) >= 2
    assert body["items"][0]["status"] == "pending_sync"


def test_get_queue_400_invalid_status_filter(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{COACH_QUEUE_BASE}?status_filter=invalid",
        headers=coach_headers,
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_get_queue_200_empty_with_synced_filter(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{COACH_QUEUE_BASE}?status_filter=synced",
        headers=coach_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pending_count"] == 0
    assert body["items"] == []


def test_post_queue_update_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        COACH_QUEUE_BASE,
        headers=coach_headers,
        json={
            "item_id": "00000000-0000-4000-8000-000000000071",
            "item_type": "session_data",
            "status": "synced",
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "synced"
    assert body["error"] is None
    assert body["id"] == "00000000-0000-4000-8000-000000000071"
    assert body["title"]
    assert body["name"]


def test_post_queue_update_400_invalid_item_type(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        COACH_QUEUE_BASE,
        headers=coach_headers,
        json={
            "item_id": "00000000-0000-4000-8000-000000000071",
            "item_type": "invalid",
            "status": "synced",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_post_queue_update_404_missing_item(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        COACH_QUEUE_BASE,
        headers=coach_headers,
        json={
            "item_id": "00000000-0000-4000-8000-000000000099",
            "item_type": "session_data",
            "status": "synced",
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "QUEUE_ITEM_NOT_FOUND"


def test_get_queue_403_viewer(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.get(COACH_QUEUE_BASE, headers=viewer_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
