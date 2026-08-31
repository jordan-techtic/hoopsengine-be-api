"""Integration tests for organization admin Edit Coach API (HE-375)."""

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
    ORG_ADMIN_COACHES_BASE,
    REGULAR_EMAIL,
    SEEDED_ORG_ID,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000094")
EDIT_COACH_ID = UUID("00000000-0000-4000-8000-000000000095")
LINKED_COACH_USER_ID = UUID("00000000-0000-4000-8000-000000000096")
SEEDED_TEAM_VARSITY_ID = UUID("00000000-0000-4000-8000-000000000097")
MISSING_COACH_ID = UUID("00000000-0000-4000-8000-000000999998")

VALID_UPDATE_PAYLOAD = {
    "full_name": "Sarah Jenkins",
    "email": "sarah.jenkins@school.edu",
    "phone": "+1 (555) 123-4567",
    "team_assignment": "Varsity Squad",
}


@pytest.fixture
def seed_org_admin_edit_coach(ensure_teams_table: None) -> None:
    """Seed a coach, linked user account, and team for edit-coach tests."""
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
                    :id, :org_id, 'Jane', 'Doe', 'jane.doe@school.edu', :team_id
                )
                ON CONFLICT (id) DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    email = EXCLUDED.email,
                    team_id = EXCLUDED.team_id
                """
            ),
            {
                "id": EDIT_COACH_ID,
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
                    email="orgadmin.coaches@test.com",
                    username="orgadmincoaches",
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
def linked_coach_user(seed_org_admin_edit_coach: None) -> None:
    """Create a coach user account linked to the seeded coach by email."""
    with Session(sync_engine) as session:
        existing = session.get(User, LINKED_COACH_USER_ID)
        if existing is None:
            session.add(
                User(
                    id=LINKED_COACH_USER_ID,
                    email="jane.doe@school.edu",
                    username="janedoecoach",
                    encrypted_password=hash_password("Coach123!"),
                    role=UserRole.COACH.value,
                    first_name="Jane",
                    last_name="Doe",
                    phone="+1 (555) 000-1111",
                    is_super_admin=False,
                    is_active=True,
                    org_id=SEEDED_ORG_ID,
                    email_confirmed_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
        else:
            existing.email = "jane.doe@school.edu"
            existing.phone = "+1 (555) 000-1111"
            existing.org_id = SEEDED_ORG_ID
            existing.role = UserRole.COACH.value
            session.commit()


def test_get_org_admin_coach_for_edit_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_edit_coach: None,
    linked_coach_user: None,
) -> None:
    response = client.get(
        f"{ORG_ADMIN_COACHES_BASE}/{EDIT_COACH_ID}",
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "ready"
    assert body["id"] == str(EDIT_COACH_ID)
    assert body["full_name"] == "Jane Doe"
    assert body["name"] == "Jane Doe"
    assert body["email"] == "jane.doe@school.edu"
    assert body["phone"] == "+1 (555) 000-1111"
    assert body["phone_number"] == "+1 (555) 000-1111"
    assert body["team_assignment"] == "Varsity Squad"
    assert body["organization"] == "Seeded Hoops Club"


def test_get_org_admin_coach_for_edit_404_not_found(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_edit_coach: None,
) -> None:
    response = client.get(
        f"{ORG_ADMIN_COACHES_BASE}/{MISSING_COACH_ID}",
        headers=org_admin_headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "COACH_NOT_FOUND"


def test_update_org_admin_coach_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_edit_coach: None,
    linked_coach_user: None,
) -> None:
    response = client.put(
        f"{ORG_ADMIN_COACHES_BASE}/{EDIT_COACH_ID}",
        headers=org_admin_headers,
        json=VALID_UPDATE_PAYLOAD,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Coach updated successfully"
    assert body["status"] == "updated"
    assert body["full_name"] == "Sarah Jenkins"
    assert body["name"] == "Sarah Jenkins"
    assert body["email"] == "sarah.jenkins@school.edu"
    assert body["phone"] == "+1 (555) 123-4567"
    assert body["team_assignment"] == "Varsity Squad"
    assert body["organization"] == "Seeded Hoops Club"

    with Session(sync_engine) as session:
        user = session.get(User, LINKED_COACH_USER_ID)
        assert user is not None
        assert user.email == "sarah.jenkins@school.edu"
        assert user.phone == "+1 (555) 123-4567"


def test_update_org_admin_coach_400_empty_full_name(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_edit_coach: None,
    linked_coach_user: None,
) -> None:
    response = client.put(
        f"{ORG_ADMIN_COACHES_BASE}/{EDIT_COACH_ID}",
        headers=org_admin_headers,
        json={**VALID_UPDATE_PAYLOAD, "full_name": "   "},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "full_name"


def test_update_org_admin_coach_400_empty_email(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_edit_coach: None,
    linked_coach_user: None,
) -> None:
    response = client.put(
        f"{ORG_ADMIN_COACHES_BASE}/{EDIT_COACH_ID}",
        headers=org_admin_headers,
        json={**VALID_UPDATE_PAYLOAD, "email": "   "},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"


def test_update_org_admin_coach_400_empty_phone(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_edit_coach: None,
    linked_coach_user: None,
) -> None:
    response = client.put(
        f"{ORG_ADMIN_COACHES_BASE}/{EDIT_COACH_ID}",
        headers=org_admin_headers,
        json={**VALID_UPDATE_PAYLOAD, "phone": "   "},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "phone"


def test_update_org_admin_coach_400_invalid_email(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_edit_coach: None,
    linked_coach_user: None,
) -> None:
    response = client.put(
        f"{ORG_ADMIN_COACHES_BASE}/{EDIT_COACH_ID}",
        headers=org_admin_headers,
        json={**VALID_UPDATE_PAYLOAD, "email": "not-an-email"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"


def test_update_org_admin_coach_409_duplicate_email(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_edit_coach: None,
    linked_coach_user: None,
) -> None:
    response = client.put(
        f"{ORG_ADMIN_COACHES_BASE}/{EDIT_COACH_ID}",
        headers=org_admin_headers,
        json={**VALID_UPDATE_PAYLOAD, "email": REGULAR_EMAIL},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "EMAIL_ALREADY_IN_USE"
    assert body["error"]["details"][0]["field"] == "email"


def test_update_org_admin_coach_forbidden_coach_403(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_org_admin_edit_coach: None,
) -> None:
    response = client.put(
        f"{ORG_ADMIN_COACHES_BASE}/{EDIT_COACH_ID}",
        headers=coach_headers,
        json=VALID_UPDATE_PAYLOAD,
    )
    assert response.status_code == 403


def test_update_org_admin_coach_forbidden_viewer_403(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_org_admin_edit_coach: None,
) -> None:
    response = client.get(
        f"{ORG_ADMIN_COACHES_BASE}/{EDIT_COACH_ID}",
        headers=viewer_headers,
    )
    assert response.status_code == 403
