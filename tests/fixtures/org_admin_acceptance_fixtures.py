"""Supplemental fixtures for org-admin acceptance integration tests (HE-367/404/424/413)."""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import text

from tests.conftest import (
    SEEDED_ORG_ID,
    SEEDED_PLAYER_BOB_ID,
    SEEDED_TEAM_VARSITY_ID,
    sync_engine,
)

PLAYER_DETAIL_ID = UUID("00000000-0000-4000-8000-000000000036")
INACTIVE_PLAYER_ID = UUID("00000000-0000-4000-8000-000000000082")


@pytest.fixture
def seed_org_admin_players(ensure_practice_plans_table: None) -> None:
    """Seed players, teams, and contact columns for HE-424 listing tests."""
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
                        SELECT 1 FROM information_schema.columns
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
                    active = true,
                    player_code = EXCLUDED.player_code
                """
            ),
            {"id": PLAYER_DETAIL_ID, "org_id": SEEDED_ORG_ID},
        )
        connection.execute(
            text(
                """
                UPDATE players
                SET email = 'bob.smith@varsityacademy.com', active = true
                WHERE id = :bob_id
                """
            ),
            {"bob_id": SEEDED_PLAYER_BOB_ID},
        )
        connection.execute(
            text(
                """
                INSERT INTO players (id, org_id, first_name, last_name, player_code, active)
                VALUES (:id, :org_id, 'Inactive', 'Player', 'PC-INACTIVE', false)
                ON CONFLICT (id) DO UPDATE SET active = false
                """
            ),
            {"id": INACTIVE_PLAYER_ID, "org_id": SEEDED_ORG_ID},
        )
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
                UPDATE players SET team_id = :team_id WHERE id = :player_id
                """
            ),
            {"team_id": SEEDED_TEAM_VARSITY_ID, "player_id": PLAYER_DETAIL_ID},
        )
