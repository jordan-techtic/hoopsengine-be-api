"""Integration tests for Team Details API (HE-337)."""

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
    REGULAR_USER_ID,
    SEEDED_ORG_ID,
    TEAMS_BASE,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000081")
EXISTING_EMAIL_USER_ID = UUID("00000000-0000-4000-8000-000000000082")
MISSING_TEAM_ID = UUID("00000000-0000-4000-8000-000000999996")

VALID_CREATE_PAYLOAD = {
    "name": "Varsity Boys",
    "email": "newcoach@school.edu",
    "season": "2025-2026",
    "home_ground": "Main Gymnasium",
    "age_group": "16-18",
    "training_schedule": "Mon/Wed 4:00 PM",
    "phone": "+1-555-0100",
    "coaches": ["Coach Taylor"],
    "players": ["Sarah Jenkins"],
}


@pytest.fixture(autouse=True)
def _team_tables(ensure_teams_table: None) -> None:
    """Ensure team tables exist for each test."""


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for an org_admin user linked to the seeded organization."""
    with Session(sync_engine) as session:
        if session.get(User, ORG_ADMIN_ID) is None:
            session.add(
                User(
                    id=ORG_ADMIN_ID,
                    email="orgadmin.teamdetails@test.com",
                    username="orgadminteamdetails",
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
def coach_view_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for a non-admin coach who can still view team details."""
    return auth_headers(create_access_token(REGULAR_USER_ID))


@pytest.fixture
def existing_email_user(seeded_users: dict) -> None:
    """Seed a user whose email should trigger duplicate-email conflicts."""
    with Session(sync_engine) as session:
        if session.get(User, EXISTING_EMAIL_USER_ID) is None:
            session.add(
                User(
                    id=EXISTING_EMAIL_USER_ID,
                    email="existingcoach@school.edu",
                    username="existingcoach",
                    encrypted_password=hash_password("Coach123!"),
                    role=UserRole.COACH.value,
                    first_name="Existing",
                    last_name="Coach",
                    is_super_admin=False,
                    is_active=True,
                    org_id=SEEDED_ORG_ID,
                    email_confirmed_at=datetime.now(timezone.utc),
                )
            )
            session.commit()


def _create_team(client: TestClient, headers: dict[str, str], payload: dict | None = None) -> str:
    response = client.post(
        TEAMS_BASE,
        headers=headers,
        json=payload or VALID_CREATE_PAYLOAD,
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_get_team_details_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    coach_view_headers: dict[str, str],
) -> None:
    team_id = _create_team(client, org_admin_headers)

    response = client.get(f"{TEAMS_BASE}/{team_id}", headers=coach_view_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["id"] == team_id
    assert body["name"] == "Varsity Boys"
    assert body["season"] == "2025-2026"
    assert body["email"] == "newcoach@school.edu"
    assert body["role"] == "head_coach"
    assert body["roles"] == ["head_coach"]
    assert body["organization"] == "Seeded Hoops Club"
    assert body["coaches"] == ["Coach Varsity"]
    assert body["phone"] is None
    assert body["message"] == "Team details loaded successfully"


def test_create_team_201(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        TEAMS_BASE,
        headers=org_admin_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Team created successfully"
    assert body["name"] == "Varsity Boys"
    assert body["email"] == "newcoach@school.edu"


def test_create_team_400_missing_required_fields(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        TEAMS_BASE,
        headers=org_admin_headers,
        json={
            "name": "",
            "email": "coach@example.com",
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "name"


def test_create_team_400_empty_email(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        TEAMS_BASE,
        headers=org_admin_headers,
        json={
            "name": "Junior Squad",
            "email": "",
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"


def test_create_team_409_duplicate_email(
    client: TestClient,
    org_admin_headers: dict[str, str],
    existing_email_user: None,
) -> None:
    response = client.post(
        TEAMS_BASE,
        headers=org_admin_headers,
        json={
            **VALID_CREATE_PAYLOAD,
            "name": "Duplicate Email Team",
            "email": "existingcoach@school.edu",
        },
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "EMAIL_ALREADY_IN_USE"
    assert body["error"]["details"][0]["field"] == "email"


def test_create_team_409_duplicate_name(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    first = client.post(
        TEAMS_BASE,
        headers=org_admin_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    assert first.status_code == 201

    duplicate = client.post(
        TEAMS_BASE,
        headers=org_admin_headers,
        json={
            **VALID_CREATE_PAYLOAD,
            "email": "anothercoach@school.edu",
        },
    )
    assert duplicate.status_code == 409
    body = duplicate.json()
    assert body["error"]["code"] == "TEAM_NAME_EXISTS"
    assert body["error"]["details"][0]["field"] == "name"


def test_update_team_200_same_email_with_linked_coach_user(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    """Updating with the primary coach's unchanged email must not 409 when a linked user exists."""
    team_id = _create_team(client, org_admin_headers)
    coach_email = "newcoach@school.edu"
    linked_coach_id = UUID("00000000-0000-4000-8000-000000000083")

    with Session(sync_engine) as session:
        if session.get(User, linked_coach_id) is None:
            session.add(
                User(
                    id=linked_coach_id,
                    email=coach_email,
                    username="linkedteamcoach",
                    encrypted_password=hash_password("Coach123!"),
                    role=UserRole.COACH.value,
                    first_name="Linked",
                    last_name="Coach",
                    is_super_admin=False,
                    is_active=True,
                    org_id=SEEDED_ORG_ID,
                    email_confirmed_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

    response = client.put(
        f"{TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
        json={
            "name": "Varsity Elite",
            "email": coach_email,
            "season": "2026-2027",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == coach_email
    assert body["name"] == "Varsity Elite"


def test_update_team_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    team_id = _create_team(client, org_admin_headers)

    response = client.put(
        f"{TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
        json={
            "name": "Varsity Elite",
            "email": "updatedcoach@school.edu",
            "season": "2026-2027",
            "role": "head_coach",
            "phone": "+1-555-0200",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Team updated successfully"
    assert body["name"] == "Varsity Elite"
    assert body["email"] == "updatedcoach@school.edu"
    assert body["season"] == "2026-2027"
    assert body["role"] == "head_coach"


def test_get_team_details_404_not_found(
    client: TestClient,
    coach_view_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{TEAMS_BASE}/{MISSING_TEAM_ID}",
        headers=coach_view_headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TEAM_NOT_FOUND"


def test_delete_team_204(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    team_id = _create_team(client, org_admin_headers)

    response = client.delete(
        f"{TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
    )
    assert response.status_code == 204
    assert response.content == b""

    missing = client.get(
        f"{TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
    )
    assert missing.status_code == 404


def test_create_team_forbidden_coach_403(
    client: TestClient,
    coach_view_headers: dict[str, str],
) -> None:
    response = client.post(
        TEAMS_BASE,
        headers=coach_view_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
