"""Integration tests for organization admin team CRUD API (HE-380, HE-372, HE-367)."""

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
from app.schemas.org_admin_team import TEAM_REMOVAL_CONFIRMATION_MESSAGE
from tests.conftest import (
    ORG_ADMIN_TEAMS_BASE,
    REGULAR_USER_ID,
    SEEDED_ORG_ID,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000071")
SEEDED_COACH_ID = UUID("00000000-0000-4000-8000-000000000072")
MISSING_TEAM_ID = UUID("00000000-0000-4000-8000-000000999998")
TEAM_WITH_PLAYER_ID = UUID("00000000-0000-4000-8000-000000000073")
PLAYER_ON_TEAM_ID = UUID("00000000-0000-4000-8000-000000000074")

VALID_REMOVAL_PAYLOAD = {"phone": "+1-555-0100"}

VALID_CREATE_PAYLOAD = {
    "team_name": "Varsity Boys",
    "team_code": "VB-2026",
    "team_description": "Competitive varsity roster for the 2026 season",
    "age_group": "16-18",
    "coaches": [
        {
            "id": str(SEEDED_COACH_ID),
            "name": "Coach Taylor",
        }
    ],
    "full_name": "Varsity Boys",
    "phone": "+1-555-0100",
}


@pytest.fixture(autouse=True)
def _team_tables(ensure_teams_table: None) -> None:
    """Ensure team tables exist for each test."""


@pytest.fixture
def seeded_org_coach(ensure_teams_table: None) -> UUID:
    """Seed one coach in the organization for assignment tests."""
    with sync_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO coaches (id, org_id, first_name, last_name, email)
                VALUES (:id, :org_id, 'Taylor', 'Reed', 'coach.taylor@test.com')
                ON CONFLICT (id) DO UPDATE SET
                    org_id = EXCLUDED.org_id,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    email = EXCLUDED.email,
                    team_id = NULL
                """
            ),
            {"id": SEEDED_COACH_ID, "org_id": SEEDED_ORG_ID},
        )
    return SEEDED_COACH_ID


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for an org_admin user linked to the seeded organization."""
    with Session(sync_engine) as session:
        if session.get(User, ORG_ADMIN_ID) is None:
            session.add(
                User(
                    id=ORG_ADMIN_ID,
                    email="orgadmin.teams@test.com",
                    username="orgadminteams",
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


@pytest.fixture
def coach_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for a coach user (non org-admin)."""
    return auth_headers(create_access_token(REGULAR_USER_ID))


def test_create_org_team_201(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seeded_org_coach: UUID,
) -> None:
    response = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["name"] == "Varsity Boys"
    assert body["code"] == "VB-2026"
    assert body["team_name"] == "Varsity Boys"
    assert body["team_code"] == "VB-2026"
    assert body["team_description"] == "Competitive varsity roster for the 2026 season"
    assert body["age_group"] == "16-18"
    assert body["organization"]
    assert len(body["coaches"]) == 1
    assert body["coaches"][0]["id"] == str(SEEDED_COACH_ID)


def test_create_org_team_400_missing_required_fields(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_headers,
        json={
            "team_name": "",
            "team_code": "",
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_create_org_team_409_duplicate_code(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seeded_org_coach: UUID,
) -> None:
    first = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    assert first.status_code == 201

    duplicate = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_headers,
        json={
            **VALID_CREATE_PAYLOAD,
            "team_name": "Another Team",
        },
    )
    assert duplicate.status_code == 409
    body = duplicate.json()
    assert body["success"] is False
    assert body["error"]["code"] == "TEAM_CODE_EXISTS"


def test_get_org_team_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seeded_org_coach: UUID,
) -> None:
    create = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    assert create.status_code == 201
    team_id = create.json()["id"]

    response = client.get(
        f"{ORG_ADMIN_TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["id"] == team_id
    assert body["name"] == "Varsity Boys"
    assert body["code"] == "VB-2026"
    assert body["description"]
    assert body["confirmation_message"] == TEAM_REMOVAL_CONFIRMATION_MESSAGE


def test_update_org_team_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seeded_org_coach: UUID,
) -> None:
    create = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    assert create.status_code == 201
    team_id = create.json()["id"]

    response = client.put(
        f"{ORG_ADMIN_TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
        json={
            "team_name": "Updated Varsity Boys",
            "team_description": "Updated roster description",
            "age_group": "17-18",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["name"] == "Updated Varsity Boys"
    assert body["team_description"] == "Updated roster description"
    assert body["age_group"] == "17-18"
    assert body["message"] == "Team updated successfully"


def test_remove_org_team_200_with_confirmation_message(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seeded_org_coach: UUID,
) -> None:
    create = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_headers,
        json={
            **VALID_CREATE_PAYLOAD,
            "team_code": "VB-DELETE",
            "coaches": [],
        },
    )
    assert create.status_code == 201
    team_id = create.json()["id"]

    response = client.delete(
        f"{ORG_ADMIN_TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
        json=VALID_REMOVAL_PAYLOAD,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["message"] == "Team removed successfully"
    assert body["status"] == "removed"
    assert body["team_id"] == team_id
    assert body["phone"] == "+1-555-0100"

    missing = client.get(
        f"{ORG_ADMIN_TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
    )
    assert missing.status_code == 404


def test_org_teams_forbidden_coach_403(
    client: TestClient,
    coach_headers: dict[str, str],
    seeded_org_coach: UUID,
) -> None:
    response = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=coach_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    assert response.status_code == 403
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "FORBIDDEN"


# --- HE-372: Edit Team (/api/v1/admin/teams/{team_id}) ---


def test_edit_team_get_with_figma_fields_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seeded_org_coach: UUID,
) -> None:
    create = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    assert create.status_code == 201
    team_id = create.json()["id"]

    response = client.get(
        f"{ORG_ADMIN_TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["id"] == team_id
    assert body["full_name"] == "Varsity Boys"
    assert body["name"] == "Varsity Boys"
    assert body["description"]
    assert body["organization"] == "Seeded Hoops Club"
    assert len(body["coaches"]) == 1
    assert body["coaches"][0]["coach_id"] == str(SEEDED_COACH_ID)


def test_edit_team_update_with_figma_fields_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seeded_org_coach: UUID,
) -> None:
    create = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    assert create.status_code == 201
    team_id = create.json()["id"]

    response = client.put(
        f"{ORG_ADMIN_TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
        json={
            "full_name": "Varsity Squad",
            "description": "Premier elite development squad preparing for state level championship.",
            "coaches": [
                {
                    "coach_id": str(SEEDED_COACH_ID),
                    "name": "Coach Dave Miller",
                }
            ],
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Team updated successfully"
    assert body["full_name"] == "Varsity Squad"
    assert body["name"] == "Varsity Squad"
    assert (
        body["description"]
        == "Premier elite development squad preparing for state level championship."
    )
    assert body["team_description"] == (
        "Premier elite development squad preparing for state level championship."
    )
    assert len(body["coaches"]) == 1
    assert body["coaches"][0]["name"] == "Coach Dave Miller"
    assert body["coaches"][0]["coach_id"] == str(SEEDED_COACH_ID)


def test_edit_team_400_empty_name(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seeded_org_coach: UUID,
) -> None:
    create = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    assert create.status_code == 201
    team_id = create.json()["id"]

    response = client.put(
        f"{ORG_ADMIN_TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
        json={"full_name": "   ", "description": "Still valid description"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "team_name"


def test_edit_team_409_duplicate_name(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seeded_org_coach: UUID,
) -> None:
    first = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    assert first.status_code == 201

    second = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_headers,
        json={
            **VALID_CREATE_PAYLOAD,
            "team_name": "Junior Boys",
            "team_code": "JB-2026",
            "full_name": "Junior Boys",
            "coaches": [],
        },
    )
    assert second.status_code == 201
    team_id = second.json()["id"]

    response = client.put(
        f"{ORG_ADMIN_TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
        json={"full_name": "Varsity Boys"},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "TEAM_NAME_EXISTS"
    assert body["error"]["details"][0]["field"] == "team_name"


def test_edit_team_403_coach_put(
    client: TestClient,
    coach_headers: dict[str, str],
    seeded_org_coach: UUID,
) -> None:
    response = client.put(
        f"{ORG_ADMIN_TEAMS_BASE}/{UUID('00000000-0000-4000-8000-000000000099')}",
        headers=coach_headers,
        json={"full_name": "Varsity Squad", "description": "Updated"},
    )
    assert response.status_code == 403


# --- HE-367: Remove Team (/api/v1/admin/teams/{team_id}) ---


def test_get_org_team_for_removal_200_includes_confirmation_message(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seeded_org_coach: UUID,
) -> None:
    create = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_headers,
        json={**VALID_CREATE_PAYLOAD, "team_code": "VB-REMOVAL"},
    )
    assert create.status_code == 201
    team_id = create.json()["id"]

    response = client.get(
        f"{ORG_ADMIN_TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["confirmation_message"] == TEAM_REMOVAL_CONFIRMATION_MESSAGE
    assert body["organization"] == "Seeded Hoops Club"
    assert body["name"] == "Varsity Boys"


def test_remove_org_team_400_missing_phone(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seeded_org_coach: UUID,
) -> None:
    create = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_headers,
        json={**VALID_CREATE_PAYLOAD, "team_code": "VB-NOPHONE", "coaches": []},
    )
    team_id = create.json()["id"]

    response = client.delete(
        f"{ORG_ADMIN_TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
        json={"phone": "   "},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"][0]["field"] == "phone"


def test_remove_org_team_400_invalid_phone(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seeded_org_coach: UUID,
) -> None:
    create = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_headers,
        json={**VALID_CREATE_PAYLOAD, "team_code": "VB-BADPHONE", "coaches": []},
    )
    team_id = create.json()["id"]

    response = client.delete(
        f"{ORG_ADMIN_TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
        json={"phone": "not-a-phone"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"][0]["field"] == "phone"


def test_remove_org_team_404_not_found(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.delete(
        f"{ORG_ADMIN_TEAMS_BASE}/{MISSING_TEAM_ID}",
        headers=org_admin_headers,
        json=VALID_REMOVAL_PAYLOAD,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TEAM_NOT_FOUND"


def test_remove_org_team_403_coach_forbidden(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.delete(
        f"{ORG_ADMIN_TEAMS_BASE}/{MISSING_TEAM_ID}",
        headers=coach_headers,
        json=VALID_REMOVAL_PAYLOAD,
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.fixture
def team_with_assigned_player(ensure_teams_table: None) -> UUID:
    """Seed a team with one assigned player for TEAM_HAS_PLAYERS guard tests."""
    with sync_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO teams (id, org_id, name)
                VALUES (:id, :org_id, 'Blocked Delete Team')
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                """
            ),
            {"id": TEAM_WITH_PLAYER_ID, "org_id": SEEDED_ORG_ID},
        )
        connection.execute(
            text(
                """
                INSERT INTO players (id, org_id, first_name, last_name, team_id, active)
                VALUES (:id, :org_id, 'Blocked', 'Player', :team_id, true)
                ON CONFLICT (id) DO UPDATE SET team_id = EXCLUDED.team_id, active = true
                """
            ),
            {
                "id": PLAYER_ON_TEAM_ID,
                "org_id": SEEDED_ORG_ID,
                "team_id": TEAM_WITH_PLAYER_ID,
            },
        )
    return TEAM_WITH_PLAYER_ID


def test_remove_org_team_409_team_has_players(
    client: TestClient,
    org_admin_headers: dict[str, str],
    team_with_assigned_player: UUID,
) -> None:
    response = client.delete(
        f"{ORG_ADMIN_TEAMS_BASE}/{team_with_assigned_player}",
        headers=org_admin_headers,
        json=VALID_REMOVAL_PAYLOAD,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TEAM_HAS_PLAYERS"
