"""Integration tests for organization admin Remove Coach API (HE-369)."""

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
from app.schemas.org_admin_coach import COACH_REMOVAL_CONFIRMATION_MESSAGE
from tests.conftest import (
    ORG_ADMIN_COACHES_BASE,
    SEEDED_ORG_ID,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000098")
REMOVE_COACH_ID = UUID("00000000-0000-4000-8000-000000000099")
SEEDED_TEAM_VARSITY_ID = UUID("00000000-0000-4000-8000-00000000009a")
MISSING_COACH_ID = UUID("00000000-0000-4000-8000-000000999997")


@pytest.fixture
def seed_org_admin_remove_coach(ensure_teams_table: None) -> None:
    """Seed a coach and team for org-admin remove-coach tests."""
    with sync_engine.begin() as connection:
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
                INSERT INTO coaches (
                    id, org_id, first_name, last_name, email, team_id
                ) VALUES (
                    :id, :org_id, 'Sarah', 'Jenkins', 'sarah.jenkins@school.edu', :team_id
                )
                ON CONFLICT (id) DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    email = EXCLUDED.email,
                    team_id = EXCLUDED.team_id
                """
            ),
            {
                "id": REMOVE_COACH_ID,
                "org_id": SEEDED_ORG_ID,
                "team_id": SEEDED_TEAM_VARSITY_ID,
            },
        )


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for an org_admin user linked to the seeded organization."""
    with Session(sync_engine) as session:
        if session.get(User, ORG_ADMIN_ID) is None:
            session.add(
                User(
                    id=ORG_ADMIN_ID,
                    email="org-admin-remove-coach@example.com",
                    username="orgadminremovecoach",
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


def test_get_org_admin_coach_for_removal_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_remove_coach: None,
) -> None:
    response = client.get(
        f"{ORG_ADMIN_COACHES_BASE}/{REMOVE_COACH_ID}",
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "ready"
    assert body["id"] == str(REMOVE_COACH_ID)
    assert body["coach_id"] == str(REMOVE_COACH_ID)
    assert body["name"] == "Sarah Jenkins"
    assert body["team"] == "Varsity Squad"
    assert body["team_assignment"] == "Varsity Squad"
    assert body["organization"] == "Seeded Hoops Club"
    assert body["confirmation_message"] == COACH_REMOVAL_CONFIRMATION_MESSAGE
    assert body["message"] == "Coach details loaded successfully"
    assert body["description"] == "Coach profile and contact information"


def test_remove_org_admin_coach_204(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_remove_coach: None,
) -> None:
    response = client.delete(
        f"{ORG_ADMIN_COACHES_BASE}/{REMOVE_COACH_ID}",
        headers=org_admin_headers,
    )
    assert response.status_code == 204
    assert response.content == b""

    with sync_engine.begin() as connection:
        row = connection.execute(
            text("SELECT id FROM coaches WHERE id = :coach_id"),
            {"coach_id": REMOVE_COACH_ID},
        ).scalar_one_or_none()
        assert row is None


def test_remove_org_admin_coach_404_not_found(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_remove_coach: None,
) -> None:
    response = client.delete(
        f"{ORG_ADMIN_COACHES_BASE}/{MISSING_COACH_ID}",
        headers=org_admin_headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "COACH_NOT_FOUND"


def test_remove_org_admin_coach_400_invalid_phone(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_remove_coach: None,
) -> None:
    response = client.request(
        "DELETE",
        f"{ORG_ADMIN_COACHES_BASE}/{REMOVE_COACH_ID}",
        headers=org_admin_headers,
        json={"phone": "not-a-phone"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "phone"


def test_remove_org_admin_coach_forbidden_coach_403(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_org_admin_remove_coach: None,
) -> None:
    response = client.delete(
        f"{ORG_ADMIN_COACHES_BASE}/{REMOVE_COACH_ID}",
        headers=coach_headers,
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"

    get_response = client.get(
        f"{ORG_ADMIN_COACHES_BASE}/{REMOVE_COACH_ID}",
        headers=coach_headers,
    )
    assert get_response.status_code == 403
    assert get_response.json()["error"]["code"] == "FORBIDDEN"
