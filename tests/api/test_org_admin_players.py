"""Integration tests for organization admin player management API (HE-426)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from tests.conftest import (
    ORG_ADMIN_PLAYERS_BASE,
    PLAYERS_BASE,
    SEEDED_ORG_ID,
    SEEDED_PLAYER_BOB_ID,
    SEEDED_PLAYER_JANE_ID,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000081")
PLAYER_DETAIL_ID = UUID("00000000-0000-4000-8000-000000000036")
INACTIVE_PLAYER_ID = UUID("00000000-0000-4000-8000-000000000082")


@pytest.fixture
def seed_org_admin_players(ensure_practice_plans_table: None) -> None:
    """Seed players with contact fields for org-admin player management tests."""
    with sync_engine.begin() as connection:
        for column, ddl in (
            ("email", "ALTER TABLE players ADD COLUMN email text"),
            ("phone", "ALTER TABLE players ADD COLUMN phone text"),
            ("position", "ALTER TABLE players ADD COLUMN position text"),
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
                SET email = 'bob.smith@varsityacademy.com', phone = '+15559876543', active = true
                WHERE id = :bob_id
                """
            ),
            {"bob_id": SEEDED_PLAYER_BOB_ID},
        )
        connection.execute(
            text(
                """
                INSERT INTO players (
                    id, org_id, first_name, last_name, player_code, active
                ) VALUES (
                    :id, :org_id, 'Inactive', 'Player', 'PC-INACTIVE', false
                )
                ON CONFLICT (id) DO UPDATE SET active = false
                """
            ),
            {"id": INACTIVE_PLAYER_ID, "org_id": SEEDED_ORG_ID},
        )


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for an org_admin user linked to the seeded organization."""
    with Session(sync_engine) as session:
        if session.get(User, ORG_ADMIN_ID) is None:
            session.add(
                User(
                    id=ORG_ADMIN_ID,
                    email="orgadmin.players@test.com",
                    username="orgadminplayers",
                    encrypted_password=hash_password("OrgAdmin123!"),
                    role=UserRole.ORG_ADMIN.value,
                    first_name="Org",
                    last_name="Admin",
                    is_super_admin=False,
                    is_active=True,
                    org_id=SEEDED_ORG_ID,
                    email_confirmed_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
    return auth_headers(create_access_token(ORG_ADMIN_ID))


def test_get_org_player_detail_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_players: None,
) -> None:
    response = client.get(
        f"{ORG_ADMIN_PLAYERS_BASE}/{PLAYER_DETAIL_ID}",
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["title"] == "Player Management"
    assert body["first_name"] == "Ava"
    assert body["last_name"] == "Morales"
    assert body["email"] == "ava.morales@varsityacademy.com"
    assert body["phone_number"] == "+1 (555) 382-9102"
    assert body["position"] == "Forward"
    assert body["id"] == str(PLAYER_DETAIL_ID)
    assert body["stats"]["games_played"] >= 0
    assert "goals" in body["stats"]
    assert "assists" in body["stats"]
    assert "yellow_cards" in body["stats"]


def test_update_org_player_400_empty_first_name(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_players: None,
) -> None:
    response = client.put(
        f"{ORG_ADMIN_PLAYERS_BASE}/{PLAYER_DETAIL_ID}",
        headers=org_admin_headers,
        json={"first_name": "   "},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "first_name"


def test_update_org_player_409_duplicate_email(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_players: None,
) -> None:
    response = client.put(
        f"{ORG_ADMIN_PLAYERS_BASE}/{PLAYER_DETAIL_ID}",
        headers=org_admin_headers,
        json={"email": "bob.smith@varsityacademy.com"},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "EMAIL_ALREADY_IN_USE"
    assert body["error"]["details"][0]["field"] == "email"


def test_update_org_player_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_players: None,
) -> None:
    response = client.put(
        f"{ORG_ADMIN_PLAYERS_BASE}/{PLAYER_DETAIL_ID}",
        headers=org_admin_headers,
        json={
            "position": "Center",
            "phone_number": "+1-555-0100",
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Player updated successfully"
    assert body["position"] == "Center"
    assert body["phone_number"] == "+1-555-0100"
    assert body["stats"]["games_played"] >= 0


def test_list_org_players_active_only_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_players: None,
) -> None:
    response = client.get(ORG_ADMIN_PLAYERS_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["title"] == "Player Management"
    assert body["error"] is None
    player_ids = {player["id"] for player in body["players"]}
    assert str(PLAYER_DETAIL_ID) in player_ids
    assert str(SEEDED_PLAYER_JANE_ID) in player_ids or str(SEEDED_PLAYER_BOB_ID) in player_ids
    assert str(INACTIVE_PLAYER_ID) not in player_ids


def test_org_players_forbidden_viewer_403(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_org_admin_players: None,
) -> None:
    response = client.get(ORG_ADMIN_PLAYERS_BASE, headers=viewer_headers)
    assert response.status_code == 403


def test_org_player_detail_same_path_as_coach(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_players: None,
) -> None:
    """Org-admin player routes share the canonical /api/v1/players paths."""
    assert ORG_ADMIN_PLAYERS_BASE == PLAYERS_BASE
    response = client.get(
        f"{PLAYERS_BASE}/{PLAYER_DETAIL_ID}",
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Player Management"
