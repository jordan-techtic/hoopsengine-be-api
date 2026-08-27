"""Integration tests for My Players API (HE-311)."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import (
    PLAYERS_BASE,
    SEEDED_ORG_ID,
    SEEDED_PLAYER_BOB_ID,
    SEEDED_PLAYER_JANE_ID,
    sync_engine,
)

SEEDED_TEAM_VARSITY_ID = UUID("00000000-0000-4000-8000-000000000042")


@pytest.fixture
def seed_my_players_data(seed_leaderboard_data: dict) -> dict:
    """Ensure teams exist and players have codes for My Players tests."""
    with sync_engine.begin() as connection:
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
        for column, ddl in (
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
                UPDATE players
                SET
                    player_code = CASE id
                        WHEN :jane_id THEN 'PC-JANEDOE1'
                        WHEN :bob_id THEN 'PC-BOBSMIT1'
                        ELSE player_code
                    END,
                    team_id = :team_id,
                    active = true
                WHERE id IN (:jane_id, :bob_id)
                """
            ),
            {
                "team_id": SEEDED_TEAM_VARSITY_ID,
                "jane_id": SEEDED_PLAYER_JANE_ID,
                "bob_id": SEEDED_PLAYER_BOB_ID,
            },
        )

    return seed_leaderboard_data


def test_list_players_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_my_players_data: dict,
) -> None:
    response = client.get(PLAYERS_BASE, headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["title"] == "My Players"
    assert body["error"] is None
    assert isinstance(body["players"], list)
    assert len(body["players"]) >= 2

    jane = next(p for p in body["players"] if p["id"] == str(SEEDED_PLAYER_JANE_ID))
    assert jane["name"] == "Jane Doe"
    assert jane["player_code"] == "PC-JANEDOE1"
    assert jane["code"] == "PC-JANEDOE1"
    assert jane["team_name"] == "Varsity Squad"


def test_search_players_200_by_name(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_my_players_data: dict,
) -> None:
    response = client.get(
        f"{PLAYERS_BASE}/search",
        headers=coach_headers,
        params={"search_query": "Jane"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["search_query"] == "Jane"
    assert len(body["players"]) == 1
    assert body["players"][0]["name"] == "Jane Doe"


def test_search_players_200_by_player_code(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_my_players_data: dict,
) -> None:
    response = client.get(
        f"{PLAYERS_BASE}/search",
        headers=coach_headers,
        params={"search_query": "PC-BOBSMIT1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["players"]) == 1
    assert body["players"][0]["name"] == "Bob Smith"
    assert body["players"][0]["player_code"] == "PC-BOBSMIT1"


def test_search_players_400_empty_query(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_my_players_data: dict,
) -> None:
    response = client.get(
        f"{PLAYERS_BASE}/search",
        headers=coach_headers,
        params={"search_query": "   "},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "search_query"


def test_get_player_detail_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_my_players_data: dict,
) -> None:
    response = client.get(
        f"{PLAYERS_BASE}/{SEEDED_PLAYER_JANE_ID}",
        headers=coach_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["name"] == "Jane Doe"
    assert body["player_code"] == "PC-JANEDOE1"
    assert body["id"] == str(SEEDED_PLAYER_JANE_ID)


def test_get_player_detail_404_invalid_id(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_my_players_data: dict,
) -> None:
    missing_id = "00000000-0000-4000-8000-000000999999"
    response = client.get(
        f"{PLAYERS_BASE}/{missing_id}",
        headers=coach_headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PLAYER_NOT_FOUND"
