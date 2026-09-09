"""Integration tests for organization admin leaderboard API (HE-404)."""

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
    ORG_ADMIN_LEADERBOARD_BASE,
    SEEDED_ORG_ID,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000081")
SEARCH_URL = f"{ORG_ADMIN_LEADERBOARD_BASE}/search"
FILTERS_URL = f"{ORG_ADMIN_LEADERBOARD_BASE}/filters"


@pytest.fixture(autouse=True)
def _leaderboard_tables(seed_leaderboard_data: dict) -> None:
    """Ensure leaderboard seed data is loaded for each test."""


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for an org_admin user linked to the seeded organization."""
    with Session(sync_engine) as session:
        if session.get(User, ORG_ADMIN_ID) is None:
            session.add(
                User(
                    id=ORG_ADMIN_ID,
                    email="orgadmin.leaderboard@test.com",
                    username="orgadminleaderboard",
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


def test_get_org_admin_leaderboard_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.get(ORG_ADMIN_LEADERBOARD_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "ready"
    assert body["organization"] == "Seeded Hoops Club"
    assert body["message"] == "Leaderboard loaded successfully"
    assert len(body["items"]) >= 2
    first = body["items"][0]
    assert first["rank"] == 1
    assert "full_name" in first
    assert "shooting_percent" in first
    assert "attempts" in first
    assert "makes" in first


def test_get_org_admin_leaderboard_403_coach_forbidden(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.get(ORG_ADMIN_LEADERBOARD_BASE, headers=coach_headers)
    assert response.status_code == 403
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "FORBIDDEN"


def test_get_org_admin_leaderboard_search_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.get(
        SEARCH_URL,
        headers=org_admin_headers,
        params={"search_query": "Jane", "phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["organization"] == "Seeded Hoops Club"
    assert body["phone"] == "+1-555-0100"
    assert len(body["items"]) == 1
    assert body["items"][0]["full_name"] == "Jane Doe"
    assert body["items"][0]["shooting_percent"] == 80


def test_get_org_admin_leaderboard_search_400_empty_query(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.get(SEARCH_URL, headers=org_admin_headers)
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_post_org_admin_leaderboard_filters_200_top(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.post(
        FILTERS_URL,
        headers=org_admin_headers,
        json={
            "filters": {"ranking": "top"},
            "full_name": "Jane Doe",
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Leaderboard filtered successfully"
    assert body["organization"] == "Seeded Hoops Club"
    assert len(body["items"]) >= 2
    assert body["items"][0]["rank"] == 1
    assert body["items"][0]["full_name"] == "Jane Doe"


def test_post_org_admin_leaderboard_filters_200_bottom(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.post(
        FILTERS_URL,
        headers=org_admin_headers,
        json={"filters": {"ranking": "bottom"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["items"]) >= 2
    assert body["items"][0]["full_name"] == "Charlie Hudson"
    assert body["items"][-1]["full_name"] == "Jane Doe"
