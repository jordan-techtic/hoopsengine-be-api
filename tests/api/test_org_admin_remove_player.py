"""Integration tests for organization admin Remove Player API (HE-260)."""

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
from app.schemas.player_removal import REMOVAL_CONFIRMATION_MESSAGE
from tests.conftest import (
    ORG_ADMIN_REMOVE_PLAYERS_BASE,
    SEEDED_ORG_ID,
    SEEDED_PLAYER_BOB_ID,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000091")
REMOVAL_PLAYER_ID = UUID("00000000-0000-4000-8000-000000000092")
SEEDED_TEAM_VARSITY_ID = UUID("00000000-0000-4000-8000-000000000093")
MISSING_PLAYER_ID = UUID("00000000-0000-4000-8000-000000999999")

VALID_REMOVAL_PAYLOAD = {
    "full_name": "Sarah Jenkins",
    "email": "sarah.jenkins@school.edu",
    "phone": "(555) 123-4567",
}


@pytest.fixture
def seed_org_admin_removal_player(ensure_practice_plans_table: None) -> None:
    """Seed a player with email, phone, and team for org-admin removal tests."""
    with sync_engine.begin() as connection:
        for column, ddl in (
            ("email", "ALTER TABLE players ADD COLUMN email text"),
            ("phone", "ALTER TABLE players ADD COLUMN phone text"),
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
                VALUES (:id, :org_id, 'Varsity Squad')
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                """
            ),
            {"id": SEEDED_TEAM_VARSITY_ID, "org_id": SEEDED_ORG_ID},
        )
        connection.execute(
            text(
                """
                INSERT INTO players (
                    id, org_id, first_name, last_name, player_code,
                    email, phone, team_id, active
                ) VALUES (
                    :id, :org_id, 'Sarah', 'Jenkins', 'PC-SARAH01',
                    'sarah.jenkins@school.edu', '(555) 123-4567', :team_id, true
                )
                ON CONFLICT (id) DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    email = EXCLUDED.email,
                    phone = EXCLUDED.phone,
                    team_id = EXCLUDED.team_id,
                    active = true
                """
            ),
            {
                "id": REMOVAL_PLAYER_ID,
                "org_id": SEEDED_ORG_ID,
                "team_id": SEEDED_TEAM_VARSITY_ID,
            },
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


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for an org_admin user linked to the seeded organization."""
    with Session(sync_engine) as session:
        if session.get(User, ORG_ADMIN_ID) is None:
            session.add(
                User(
                    id=ORG_ADMIN_ID,
                    email="orgadmin.remove@test.com",
                    username="orgadminremove",
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


def test_get_org_admin_removal_detail_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_removal_player: None,
) -> None:
    response = client.get(
        f"{ORG_ADMIN_REMOVE_PLAYERS_BASE}/{REMOVAL_PLAYER_ID}/removal",
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["confirmation_message"] == REMOVAL_CONFIRMATION_MESSAGE
    assert body["description"] == REMOVAL_CONFIRMATION_MESSAGE
    assert body["full_name"] == "Sarah Jenkins"
    assert body["name"] == "Sarah Jenkins"
    assert body["email"] == "sarah.jenkins@school.edu"
    assert body["phone_number"] == "(555) 123-4567"
    assert body["phone"] == "(555) 123-4567"
    assert body["team"] == "Varsity Squad"
    assert body["player_id"] == str(REMOVAL_PLAYER_ID)
    assert body["organization"]


def test_remove_org_admin_player_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_removal_player: None,
) -> None:
    response = client.request(
        "DELETE",
        f"{ORG_ADMIN_REMOVE_PLAYERS_BASE}/{REMOVAL_PLAYER_ID}",
        headers=org_admin_headers,
        json=VALID_REMOVAL_PAYLOAD,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Player removed successfully"
    assert body["full_name"] == "Sarah Jenkins"
    assert body["email"] == "sarah.jenkins@school.edu"
    assert body["player_id"] == str(REMOVAL_PLAYER_ID)
    assert body["organization"]

    follow_up = client.get(
        f"{ORG_ADMIN_REMOVE_PLAYERS_BASE}/{REMOVAL_PLAYER_ID}/removal",
        headers=org_admin_headers,
    )
    assert follow_up.status_code == 404


def test_remove_org_admin_player_400_invalid_phone(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_removal_player: None,
) -> None:
    response = client.request(
        "DELETE",
        f"{ORG_ADMIN_REMOVE_PLAYERS_BASE}/{REMOVAL_PLAYER_ID}",
        headers=org_admin_headers,
        json={**VALID_REMOVAL_PAYLOAD, "phone": "abc"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "phone"


def test_remove_org_admin_player_400_invalid_email(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_removal_player: None,
) -> None:
    response = client.request(
        "DELETE",
        f"{ORG_ADMIN_REMOVE_PLAYERS_BASE}/{REMOVAL_PLAYER_ID}",
        headers=org_admin_headers,
        json={**VALID_REMOVAL_PAYLOAD, "email": "not-an-email"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"


def test_remove_org_admin_player_404_not_found(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_removal_player: None,
) -> None:
    response = client.request(
        "DELETE",
        f"{ORG_ADMIN_REMOVE_PLAYERS_BASE}/{MISSING_PLAYER_ID}",
        headers=org_admin_headers,
        json=VALID_REMOVAL_PAYLOAD,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PLAYER_NOT_FOUND"


def test_remove_org_admin_player_409_email_already_registered(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_removal_player: None,
) -> None:
    response = client.request(
        "DELETE",
        f"{ORG_ADMIN_REMOVE_PLAYERS_BASE}/{REMOVAL_PLAYER_ID}",
        headers=org_admin_headers,
        json={
            **VALID_REMOVAL_PAYLOAD,
            "email": "bob.smith@varsityacademy.com",
        },
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "EMAIL_ALREADY_IN_USE"
    assert body["error"]["details"][0]["field"] == "email"


def test_remove_org_admin_player_403_coach_forbidden(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_org_admin_removal_player: None,
) -> None:
    response = client.request(
        "DELETE",
        f"{ORG_ADMIN_REMOVE_PLAYERS_BASE}/{REMOVAL_PLAYER_ID}",
        headers=coach_headers,
        json=VALID_REMOVAL_PAYLOAD,
    )
    assert response.status_code == 403
