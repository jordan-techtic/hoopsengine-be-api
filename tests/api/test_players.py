"""Integration tests for player detail API (HE-328)."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import (
    PLAYERS_BASE,
    SEEDED_ORG_ID,
    SEEDED_PLAYER_JANE_ID,
    SEEDED_PLAYER_BOB_ID,
    sync_engine,
)

PLAYER_DETAIL_ID = UUID("00000000-0000-4000-8000-000000000036")
SEEDED_TEAM_A_ID = UUID("00000000-0000-4000-8000-000000000041")

VALID_CREATE_PAYLOAD = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "phone_number": "1234567890",
    "gender": "Male",
    "date_of_birth": "2000-01-01",
    "team_selection": "Team A",
    "phone": "+1-555-0100",
}


@pytest.fixture
def seed_add_player_context(ensure_practice_plans_table: None) -> None:
    """Ensure player and team columns exist for add-player API tests."""
    with sync_engine.begin() as connection:
        for column, ddl in (
            ("email", "ALTER TABLE players ADD COLUMN email text"),
            ("phone", "ALTER TABLE players ADD COLUMN phone text"),
            ("gender", "ALTER TABLE players ADD COLUMN gender text"),
            ("birthdate", "ALTER TABLE players ADD COLUMN birthdate date"),
            ("team_id", "ALTER TABLE players ADD COLUMN team_id uuid"),
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
                CREATE TABLE IF NOT EXISTS public.teams (
                    id uuid PRIMARY KEY,
                    org_id uuid NOT NULL,
                    name text NOT NULL,
                    created_at timestamptz DEFAULT now()
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO teams (id, org_id, name)
                VALUES (:id, :org_id, 'Team A')
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                """
            ),
            {"id": SEEDED_TEAM_A_ID, "org_id": SEEDED_ORG_ID},
        )


@pytest.fixture
def seed_player_details(ensure_practice_plans_table: None) -> None:
    """Seed players with email and phone columns for detail API tests."""
    with sync_engine.begin() as connection:
        for column, ddl in (
            ("email", "ALTER TABLE players ADD COLUMN email text"),
            ("phone", "ALTER TABLE players ADD COLUMN phone text"),
            ("position", "ALTER TABLE players ADD COLUMN position text"),
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
                    email, phone, position, active
                ) VALUES (
                    :id, :org_id, 'Ava', 'Morales', 'PC-AVA001',
                    'ava.morales@varsityacademy.com', '+1 (555) 382-9102', 'Forward', true
                )
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    phone = EXCLUDED.phone,
                    position = EXCLUDED.position,
                    active = true
                """
            ),
            {"id": PLAYER_DETAIL_ID, "org_id": SEEDED_ORG_ID},
        )
        connection.execute(
            text(
                """
                UPDATE players
                SET email = 'bob.smith@varsityacademy.com', phone = '+15559876543'
                WHERE id = :bob_id
                """
            ),
            {"bob_id": SEEDED_PLAYER_BOB_ID},
        )


def test_create_player_201(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_add_player_context: None,
) -> None:
    response = client.post(PLAYERS_BASE, headers=coach_headers, json=VALID_CREATE_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Player added successfully"
    assert body["status"] == "created"
    assert body["title"] == "Add Player"
    assert body["first_name"] == "John"
    assert body["last_name"] == "Doe"
    assert body["email"] == "john.doe@example.com"
    assert body["phone_number"] == "1234567890"
    assert body["gender"] == "Male"
    assert body["date_of_birth"] == "2000-01-01"
    assert body["team_selection"] == "Team A"
    assert body["team"] == "Team A"
    assert body["name"] == "John Doe"
    assert "id" in body


def test_create_player_400_empty_email(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_add_player_context: None,
) -> None:
    payload = {**VALID_CREATE_PAYLOAD, "email": ""}
    response = client.post(PLAYERS_BASE, headers=coach_headers, json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"


def test_create_player_400_empty_first_name(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_add_player_context: None,
) -> None:
    payload = {**VALID_CREATE_PAYLOAD, "first_name": "   "}
    response = client.post(PLAYERS_BASE, headers=coach_headers, json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["field"] == "first_name"


def test_create_player_400_invalid_email(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_add_player_context: None,
) -> None:
    payload = {**VALID_CREATE_PAYLOAD, "email": "not-an-email"}
    response = client.post(PLAYERS_BASE, headers=coach_headers, json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"][0]["field"] == "email"


def test_create_player_400_invalid_phone(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_add_player_context: None,
) -> None:
    payload = {**VALID_CREATE_PAYLOAD, "phone_number": "abc"}
    response = client.post(PLAYERS_BASE, headers=coach_headers, json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"][0]["field"] == "phone_number"


def test_create_player_409_duplicate_email(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_add_player_context: None,
    seed_player_details: None,
) -> None:
    payload = {**VALID_CREATE_PAYLOAD, "email": "bob.smith@varsityacademy.com"}
    response = client.post(PLAYERS_BASE, headers=coach_headers, json=payload)
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "EMAIL_ALREADY_IN_USE"
    assert body["error"]["details"][0]["field"] == "email"


def test_create_player_403_non_coach(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_add_player_context: None,
) -> None:
    response = client.post(PLAYERS_BASE, headers=viewer_headers, json=VALID_CREATE_PAYLOAD)
    assert response.status_code == 403


def test_get_player_detail_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_player_details: None,
) -> None:
    response = client.get(
        f"{PLAYERS_BASE}/{PLAYER_DETAIL_ID}",
        headers=coach_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["title"] == "Player Details"
    assert body["name"] == "Ava Morales"
    assert body["email"] == "ava.morales@varsityacademy.com"
    assert body["phone_number"] == "+1 (555) 382-9102"
    assert body["position"] == "Forward"
    assert body["player_id"] == str(PLAYER_DETAIL_ID)
    assert "games_played" in body
    assert "goals" in body


def test_get_player_detail_404(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_player_details: None,
) -> None:
    missing_id = "00000000-0000-4000-8000-000000999999"
    response = client.get(
        f"{PLAYERS_BASE}/{missing_id}",
        headers=coach_headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PLAYER_NOT_FOUND"


def test_update_player_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_player_details: None,
) -> None:
    response = client.put(
        f"{PLAYERS_BASE}/{PLAYER_DETAIL_ID}",
        headers=coach_headers,
        json={"position": "Center", "phone_number": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Player updated successfully"
    assert body["position"] == "Center"


def test_update_player_400_invalid_email(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_player_details: None,
) -> None:
    response = client.put(
        f"{PLAYERS_BASE}/{PLAYER_DETAIL_ID}",
        headers=coach_headers,
        json={"email": "not-an-email"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"][0]["field"] == "email"


def test_update_player_409_duplicate_email(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_player_details: None,
) -> None:
    response = client.put(
        f"{PLAYERS_BASE}/{PLAYER_DETAIL_ID}",
        headers=coach_headers,
        json={"email": "bob.smith@varsityacademy.com"},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "EMAIL_ALREADY_IN_USE"
    assert body["error"]["details"][0]["field"] == "email"


def test_update_player_403_non_coach(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_details: None,
) -> None:
    response = client.put(
        f"{PLAYERS_BASE}/{PLAYER_DETAIL_ID}",
        headers=viewer_headers,
        json={"email": "new.email@example.com"},
    )
    assert response.status_code == 403


def test_delete_player_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_player_details: None,
) -> None:
    response = client.delete(
        f"{PLAYERS_BASE}/{SEEDED_PLAYER_JANE_ID}",
        headers=coach_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Player removed successfully"
    assert body["player_id"] == str(SEEDED_PLAYER_JANE_ID)

    follow_up = client.get(
        f"{PLAYERS_BASE}/{SEEDED_PLAYER_JANE_ID}",
        headers=coach_headers,
    )
    assert follow_up.status_code == 404
