"""Shared seed data and constants for org-admin HE ticket integration tests."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from tests.conftest import (
    SEEDED_ORG_ID,
    SEEDED_PLAYER_BOB_ID,
    TEST_VALID_PASSWORD,
    auth_headers,
    create_access_token,
    sync_engine,
)

HE_ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-0000000000e1")
HE_PLAYER_ID = UUID("00000000-0000-4000-8000-0000000000e2")
HE_COACH_ID = UUID("00000000-0000-4000-8000-0000000000e3")
HE_COACH_USER_ID = UUID("00000000-0000-4000-8000-0000000000e4")
HE_TEAM_ID = UUID("00000000-0000-4000-8000-0000000000e5")
MISSING_PLAYER_ID = UUID("00000000-0000-4000-8000-000000999991")
MISSING_COACH_ID = UUID("00000000-0000-4000-8000-000000999992")
MISSING_TEAM_ID = UUID("00000000-0000-4000-8000-000000999993")


def seed_he_ticket_org_admin_headers() -> dict[str, str]:
    with Session(sync_engine) as session:
        if session.get(User, HE_ORG_ADMIN_ID) is None:
            session.add(
                User(
                    id=HE_ORG_ADMIN_ID,
                    email="orgadmin.he.tickets@test.com",
                    username="orgadminhetickets",
                    encrypted_password=hash_password(TEST_VALID_PASSWORD),
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
    return auth_headers(create_access_token(HE_ORG_ADMIN_ID))


@pytest.fixture
def seed_he_ticket_player(ensure_practice_plans_table: None) -> None:
    with sync_engine.begin() as conn:
        for column, ddl in (
            ("email", "ALTER TABLE players ADD COLUMN email text"),
            ("phone", "ALTER TABLE players ADD COLUMN phone text"),
        ):
            exists = conn.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'players' AND column_name = :c
                    )
                    """
                ),
                {"c": column},
            ).scalar()
            if not exists:
                conn.execute(text(ddl))
        conn.execute(
            text(
                """
                INSERT INTO players (id, org_id, first_name, last_name, player_code, email, phone, active)
                VALUES (:id, :org_id, 'Ava', 'Morales', 'PC-HE378', 'ava.he378@test.com', '+15551234567', true)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email, phone = EXCLUDED.phone
                """
            ),
            {"id": HE_PLAYER_ID, "org_id": SEEDED_ORG_ID},
        )
        conn.execute(
            text(
                """
                UPDATE players
                SET email = 'bob.smith@varsityacademy.com', active = true
                WHERE id = :bob_id
                """
            ),
            {"bob_id": SEEDED_PLAYER_BOB_ID},
        )


@pytest.fixture
def seed_he_ticket_coach(ensure_teams_table: None) -> None:
    with sync_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO teams (id, org_id, name)
                VALUES (:id, :org_id, 'Varsity Squad')
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                """
            ),
            {"id": HE_TEAM_ID, "org_id": SEEDED_ORG_ID},
        )
        conn.execute(
            text(
                """
                INSERT INTO coaches (id, org_id, first_name, last_name, email, team_id)
                VALUES (:id, :org_id, 'Jane', 'Doe', 'jane.he375@test.com', :team_id)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email, team_id = EXCLUDED.team_id
                """
            ),
            {"id": HE_COACH_ID, "org_id": SEEDED_ORG_ID, "team_id": HE_TEAM_ID},
        )


@pytest.fixture
def seed_he_ticket_team(ensure_teams_table: None) -> None:
    with sync_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO teams (id, org_id, name, description, level)
                VALUES (:id, :org_id, 'Varsity Squad', 'Edit team seed', 'U16')
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                """
            ),
            {"id": HE_TEAM_ID, "org_id": SEEDED_ORG_ID},
        )
