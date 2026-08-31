"""Integration tests for organization admin Invite Coach API (HE-363)."""

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
    ORG_ADMIN_INVITE_COACH_BASE,
    ORG_ADMIN_SEARCH_COACHES_BASE,
    REGULAR_EMAIL,
    SEEDED_ORG_ID,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000098")
SEEDED_COACH_AVA_ID = UUID("00000000-0000-4000-8000-000000000099")
SEEDED_COACH_NOAH_ID = UUID("00000000-0000-4000-8000-00000000009a")

VALID_INVITE_PAYLOAD = {
    "email": "ava.morales@academy.org",
    "phone": "+1-555-0100",
    "company": "Acme Realty",
}


@pytest.fixture
def seed_invite_coaches(ensure_teams_table: None) -> None:
    """Seed coaches and invitation columns for invite/search tests."""
    with sync_engine.begin() as connection:
        for column, ddl in (
            ("invite_token", "ALTER TABLE coaches ADD COLUMN invite_token text UNIQUE"),
            ("invite_accepted", "ALTER TABLE coaches ADD COLUMN invite_accepted boolean DEFAULT false"),
        ):
            exists = connection.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'coaches'
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
                INSERT INTO coaches (
                    id, org_id, first_name, last_name, email, invite_accepted
                ) VALUES (
                    :id, :org_id, 'Noah', 'Patel', 'noah.patel@academy.org', true
                )
                ON CONFLICT (id) DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    email = EXCLUDED.email,
                    invite_accepted = true,
                    invite_token = NULL
                """
            ),
            {"id": SEEDED_COACH_NOAH_ID, "org_id": SEEDED_ORG_ID},
        )


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for an org_admin user linked to the seeded organization."""
    with Session(sync_engine) as session:
        if session.get(User, ORG_ADMIN_ID) is None:
            session.add(
                User(
                    id=ORG_ADMIN_ID,
                    email="orgadmin.invite@test.com",
                    username="orgadmininvite",
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


def test_invite_coach_201(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_invite_coaches: None,
) -> None:
    response = client.post(
        ORG_ADMIN_INVITE_COACH_BASE,
        headers=org_admin_headers,
        json=VALID_INVITE_PAYLOAD,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "invited"
    assert body["email"] == "ava.morales@academy.org"
    assert body["organization"] == "Seeded Hoops Club"
    assert body["address"] == "1 Court Ave"
    assert "coach" in body["roles"]
    assert body["link"]
    assert body["id"]


def test_invite_coach_400_empty_email(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_invite_coaches: None,
) -> None:
    response = client.post(
        ORG_ADMIN_INVITE_COACH_BASE,
        headers=org_admin_headers,
        json={"email": "   ", "phone": "+1-555-0100"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"


def test_invite_coach_400_invalid_email(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_invite_coaches: None,
) -> None:
    response = client.post(
        ORG_ADMIN_INVITE_COACH_BASE,
        headers=org_admin_headers,
        json={"email": "not-an-email"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"


def test_invite_coach_409_duplicate_email_in_org(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_invite_coaches: None,
) -> None:
    first = client.post(
        ORG_ADMIN_INVITE_COACH_BASE,
        headers=org_admin_headers,
        json=VALID_INVITE_PAYLOAD,
    )
    assert first.status_code == 201

    duplicate = client.post(
        ORG_ADMIN_INVITE_COACH_BASE,
        headers=org_admin_headers,
        json=VALID_INVITE_PAYLOAD,
    )
    assert duplicate.status_code == 409
    body = duplicate.json()
    assert body["error"]["code"] == "EMAIL_ALREADY_IN_USE"
    assert body["error"]["details"][0]["field"] == "email"


def test_invite_coach_409_existing_user_email(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_invite_coaches: None,
) -> None:
    response = client.post(
        ORG_ADMIN_INVITE_COACH_BASE,
        headers=org_admin_headers,
        json={"email": REGULAR_EMAIL},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "EMAIL_ALREADY_IN_USE"


def test_search_coaches_returns_matches(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_invite_coaches: None,
) -> None:
    invite = client.post(
        ORG_ADMIN_INVITE_COACH_BASE,
        headers=org_admin_headers,
        json=VALID_INVITE_PAYLOAD,
    )
    assert invite.status_code == 201

    response = client.get(
        ORG_ADMIN_SEARCH_COACHES_BASE,
        headers=org_admin_headers,
        params={"search_query": "Ava", "phone": "+1-555-0100", "company": "Acme Realty"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["organization"] == "Seeded Hoops Club"
    assert body["address"] == "1 Court Ave"
    assert body["search_query"] == "Ava"
    assert "coach" in body["roles"]
    names = {coach["name"] for coach in body["coaches"]}
    assert "Ava Morales" in names
    invited = next(coach for coach in body["coaches"] if coach["name"] == "Ava Morales")
    assert invited["status"] == "invited"
    assert invited["email"] == "ava.morales@academy.org"


def test_search_coaches_returns_all_when_query_empty(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_invite_coaches: None,
) -> None:
    response = client.get(
        ORG_ADMIN_SEARCH_COACHES_BASE,
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["coaches"]) >= 1
    assert any(coach["name"] == "Noah Patel" for coach in body["coaches"])
    assert any(coach["status"] == "active" for coach in body["coaches"])


def test_invite_coach_forbidden_coach_403(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_invite_coaches: None,
) -> None:
    response = client.post(
        ORG_ADMIN_INVITE_COACH_BASE,
        headers=coach_headers,
        json=VALID_INVITE_PAYLOAD,
    )
    assert response.status_code == 403


def test_search_coaches_forbidden_coach_403(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_invite_coaches: None,
) -> None:
    response = client.get(
        ORG_ADMIN_SEARCH_COACHES_BASE,
        headers=coach_headers,
    )
    assert response.status_code == 403
