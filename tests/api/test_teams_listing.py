"""Integration tests for Team Listing API (HE-334)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
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

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000083")

VALID_LISTING_CREATE_PAYLOAD = {
    "name": "Varsity Squad",
    "age_group": "U16",
    "coaches": [{"name": "John Doe"}],
    "players": [{"name": "Player One"}, {"name": "Player Two"}],
    "phone": "+1-555-0100",
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
                    email="orgadmin.teamlisting@test.com",
                    username="orgadminteamlisting",
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
    """Bearer token for a non-admin coach."""
    return auth_headers(create_access_token(REGULAR_USER_ID))


def _create_listing_team(client: TestClient, headers: dict[str, str], name: str) -> str:
    response = client.post(
        TEAMS_BASE,
        headers=headers,
        json={**VALID_LISTING_CREATE_PAYLOAD, "name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_list_teams_200_with_pagination(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    _create_listing_team(client, org_admin_headers, "Alpha Team")
    _create_listing_team(client, org_admin_headers, "Beta Team")

    response = client.get(
        TEAMS_BASE,
        headers=org_admin_headers,
        params={"page": 1, "page_size": 10},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "ready"
    assert body["organization"] == "Seeded Hoops Club"
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["total"] >= 2
    assert len(body["items"]) >= 2
    names = {item["name"] for item in body["items"]}
    assert "Alpha Team" in names
    assert "Beta Team" in names
    first = next(item for item in body["items"] if item["name"] == "Alpha Team")
    assert first["status"] == "active"
    assert first["age_group"] == "U16"
    assert first["coaches"] == ["John Doe"]
    assert first["players"] == ["Player One", "Player Two"]


def test_search_teams_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    _create_listing_team(client, org_admin_headers, "Varsity Squad")
    _create_listing_team(client, org_admin_headers, "Junior Squad")

    response = client.get(
        f"{TEAMS_BASE}/search",
        headers=org_admin_headers,
        params={"query": "Varsity", "page": 1, "page_size": 10},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["search_query"] == "Varsity"
    assert body["message"] == "Teams matching your search"
    assert len(body["items"]) >= 1
    assert all("Varsity" in item["name"] for item in body["items"])


def test_search_teams_400_empty_query(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{TEAMS_BASE}/search",
        headers=org_admin_headers,
        params={"query": "   "},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "query"


def test_create_listing_team_201(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        TEAMS_BASE,
        headers=org_admin_headers,
        json=VALID_LISTING_CREATE_PAYLOAD,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Team created successfully"
    assert body["name"] == "Varsity Squad"
    assert body["age_group"] == "U16"
    assert body["coaches"] == ["John Doe"]
    assert body["players"] == ["Player One", "Player Two"]


def test_create_listing_team_400_missing_required_fields(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        TEAMS_BASE,
        headers=org_admin_headers,
        json={"name": "Incomplete Team", "phone": "+1-555-0100"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "age_group"


def test_create_listing_team_409_duplicate_name(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    first = client.post(
        TEAMS_BASE,
        headers=org_admin_headers,
        json=VALID_LISTING_CREATE_PAYLOAD,
    )
    assert first.status_code == 201

    duplicate = client.post(
        TEAMS_BASE,
        headers=org_admin_headers,
        json={
            **VALID_LISTING_CREATE_PAYLOAD,
            "coaches": [{"name": "Another Coach"}],
        },
    )
    assert duplicate.status_code == 409
    body = duplicate.json()
    assert body["error"]["code"] == "TEAM_NAME_EXISTS"
    assert body["error"]["details"][0]["field"] == "name"


def test_list_teams_forbidden_coach_403(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(TEAMS_BASE, headers=coach_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
