"""Integration tests for organization admin practice plan CRUD API (HE-402)."""

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
    ORG_ADMIN_PRACTICE_PLANS_BASE,
    REGULAR_USER_ID,
    SEEDED_ORG_ID,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000061")

VALID_CREATE_PAYLOAD = {
    "name": "Shooting Fundamentals",
    "description": "Weekly shooting progression for varsity players",
    "drills": [
        {
            "drill_name": "Spot Up",
            "drill_description": "Catch-and-shoot from the wing",
        }
    ],
    "phone": "+1-555-0100",
}


@pytest.fixture(autouse=True)
def _practice_plan_tables(ensure_practice_plans_table: None) -> None:
    """Ensure practice plan tables exist for each test."""


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for an org_admin user linked to the seeded organization."""
    with Session(sync_engine) as session:
        if session.get(User, ORG_ADMIN_ID) is None:
            session.add(
                User(
                    id=ORG_ADMIN_ID,
                    email="orgadmin.practiceplans@test.com",
                    username="orgadminplans",
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


def test_create_org_practice_plan_201(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        ORG_ADMIN_PRACTICE_PLANS_BASE,
        headers=org_admin_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["name"] == "Shooting Fundamentals"
    assert body["title"] == "Shooting Fundamentals"
    assert body["status"] == "active"
    assert body["drill_count"] == 1
    assert body["organization"]
    assert len(body["drills"]) == 1
    assert body["drills"][0]["drill_name"] == "Spot Up"
    assert body["drills"][0]["drill_description"] == "Catch-and-shoot from the wing"


def test_create_org_practice_plan_409_duplicate_name(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    first = client.post(
        ORG_ADMIN_PRACTICE_PLANS_BASE,
        headers=org_admin_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    assert first.status_code == 201

    duplicate = client.post(
        ORG_ADMIN_PRACTICE_PLANS_BASE,
        headers=org_admin_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "PRACTICE_PLAN_NAME_EXISTS"


def test_create_org_practice_plan_400_missing_name(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    payload = {**VALID_CREATE_PAYLOAD, "name": "   "}
    response = client.post(
        ORG_ADMIN_PRACTICE_PLANS_BASE,
        headers=org_admin_headers,
        json=payload,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_list_org_practice_plans_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    create = client.post(
        ORG_ADMIN_PRACTICE_PLANS_BASE,
        headers=org_admin_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    assert create.status_code == 201

    inactive_payload = {
        "name": "Inactive Org Plan",
        "description": "Temporary plan",
        "drills": [
            {
                "drill_name": "Free Throw Line",
                "drill_description": "Form shooting",
            }
        ],
    }
    inactive = client.post(
        ORG_ADMIN_PRACTICE_PLANS_BASE,
        headers=org_admin_headers,
        json=inactive_payload,
    )
    plan_id = inactive.json()["id"]
    delete = client.delete(
        f"{ORG_ADMIN_PRACTICE_PLANS_BASE}/{plan_id}",
        headers=org_admin_headers,
    )
    assert delete.status_code == 204

    response = client.get(ORG_ADMIN_PRACTICE_PLANS_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "ready"
    assert body["organization"]
    assert len(body["plans"]) == 1
    assert body["plans"][0]["name"] == "Shooting Fundamentals"
    assert body["plans"][0]["title"] == "Shooting Fundamentals"
    assert body["plans"][0]["drill_count"] == 1
    assert body["plans"][0]["created_by_name"]


def test_update_org_practice_plan_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    create = client.post(
        ORG_ADMIN_PRACTICE_PLANS_BASE,
        headers=org_admin_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    plan_id = create.json()["id"]

    update_payload = {
        "name": "Updated Warmup Plan",
        "description": "Revised warmup sequence",
        "drills": [
            {
                "drill_name": "Free Throw Line",
                "drill_description": "Form shooting at the line",
            }
        ],
        "phone": "+1-555-0100",
    }
    response = client.put(
        f"{ORG_ADMIN_PRACTICE_PLANS_BASE}/{plan_id}",
        headers=org_admin_headers,
        json=update_payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["name"] == "Updated Warmup Plan"
    assert body["title"] == "Updated Warmup Plan"
    assert body["drill_count"] == 1
    assert body["drills"][0]["drill_name"] == "Free Throw Line"


def test_update_org_practice_plan_404(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    missing_id = "00000000-0000-4000-8000-000000999999"
    response = client.put(
        f"{ORG_ADMIN_PRACTICE_PLANS_BASE}/{missing_id}",
        headers=org_admin_headers,
        json={"name": "Missing Plan"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRACTICE_PLAN_NOT_FOUND"


def test_delete_org_practice_plan_204(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    create = client.post(
        ORG_ADMIN_PRACTICE_PLANS_BASE,
        headers=org_admin_headers,
        json=VALID_CREATE_PAYLOAD,
    )
    plan_id = create.json()["id"]

    response = client.delete(
        f"{ORG_ADMIN_PRACTICE_PLANS_BASE}/{plan_id}",
        headers=org_admin_headers,
    )
    assert response.status_code == 204

    listed = client.get(ORG_ADMIN_PRACTICE_PLANS_BASE, headers=org_admin_headers)
    assert listed.status_code == 200
    assert listed.json()["plans"] == []


def test_org_practice_plans_forbidden_coach_403(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(ORG_ADMIN_PRACTICE_PLANS_BASE, headers=coach_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
