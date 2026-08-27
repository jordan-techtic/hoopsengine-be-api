"""Integration tests for coach Remove Player API (HE-325)."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.schemas.player_removal import REMOVAL_CONFIRMATION_MESSAGE
from tests.conftest import (
    COACH_CONFIRM_REMOVAL_BASE,
    COACH_REMOVE_PLAYER_BASE,
    SEEDED_ORG_ID,
    SEEDED_PLAYER_JANE_ID,
    sync_engine,
)

REMOVAL_PLAYER_ID = UUID("00000000-0000-4000-8000-000000000037")


@pytest.fixture
def seed_removal_player(ensure_practice_plans_table: None) -> None:
    """Seed a player with email and phone for removal API tests."""
    with sync_engine.begin() as connection:
        for column, ddl in (
            ("email", "ALTER TABLE players ADD COLUMN email text"),
            ("phone", "ALTER TABLE players ADD COLUMN phone text"),
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
                    email, phone, active
                ) VALUES (
                    :id, :org_id, 'Sarah', 'Jenkins', 'PC-SARAH01',
                    'sarah.jenkins@school.edu', '(555) 123-4567', true
                )
                ON CONFLICT (id) DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    email = EXCLUDED.email,
                    phone = EXCLUDED.phone,
                    active = true
                """
            ),
            {"id": REMOVAL_PLAYER_ID, "org_id": SEEDED_ORG_ID},
        )
        connection.execute(
            text(
                """
                UPDATE players
                SET active = true
                WHERE id = :jane_id
                """
            ),
            {"jane_id": SEEDED_PLAYER_JANE_ID},
        )


def test_confirm_removal_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(COACH_CONFIRM_REMOVAL_BASE, headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["confirmation_message"] == REMOVAL_CONFIRMATION_MESSAGE
    assert body["description"] == REMOVAL_CONFIRMATION_MESSAGE
    assert body["can_remove"] is False


def test_confirm_removal_can_remove_when_fields_valid(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(
        COACH_CONFIRM_REMOVAL_BASE,
        headers=coach_headers,
        params={
            "full_name": "Sarah Jenkins",
            "email": "sarah.jenkins@school.edu",
            "phone": "(555) 123-4567",
        },
    )
    assert response.status_code == 200
    assert response.json()["can_remove"] is True


def test_remove_player_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_removal_player: None,
) -> None:
    response = client.post(
        COACH_REMOVE_PLAYER_BASE,
        headers=coach_headers,
        json={
            "full_name": "Sarah Jenkins",
            "email": "sarah.jenkins@school.edu",
            "phone": "(555) 123-4567",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Player removed successfully"
    assert body["email"] == "sarah.jenkins@school.edu"
    assert body["full_name"] == "Sarah Jenkins"
    assert body["player_id"] == str(REMOVAL_PLAYER_ID)

    follow_up = client.get(
        f"/api/v1/players/{REMOVAL_PLAYER_ID}",
        headers=coach_headers,
    )
    assert follow_up.status_code == 404


def test_remove_player_400_empty_email(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_removal_player: None,
) -> None:
    response = client.post(
        COACH_REMOVE_PLAYER_BASE,
        headers=coach_headers,
        json={
            "full_name": "Sarah Jenkins",
            "email": "",
            "phone": "(555) 123-4567",
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"


def test_remove_player_409_not_found(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_removal_player: None,
) -> None:
    response = client.post(
        COACH_REMOVE_PLAYER_BASE,
        headers=coach_headers,
        json={
            "full_name": "Missing Player",
            "email": "missing.player@school.edu",
            "phone": "(555) 999-0000",
        },
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "PLAYER_NOT_FOUND"


def test_remove_player_403_non_coach(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_removal_player: None,
) -> None:
    response = client.post(
        COACH_REMOVE_PLAYER_BASE,
        headers=viewer_headers,
        json={
            "full_name": "Sarah Jenkins",
            "email": "sarah.jenkins@school.edu",
            "phone": "(555) 123-4567",
        },
    )
    assert response.status_code == 403
