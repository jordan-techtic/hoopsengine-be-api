"""Integration tests for organization admin practice plan assignment API (HE-383)."""

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
    PRACTICE_PLANS_BASE,
    SEEDED_ORG_ID,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000081")
SEEDED_COACH_ID = UUID("00000000-0000-4000-8000-000000000072")
SEEDED_TEAM_ID = UUID("00000000-0000-4000-8000-000000000082")
SEEDED_PLAN_ID = UUID("00000000-0000-4000-8000-000000000083")

ASSIGN_URL = f"{PRACTICE_PLANS_BASE}/assign"


@pytest.fixture(autouse=True)
def _assignment_tables(ensure_practice_plan_assignments_table: None) -> None:
    """Ensure assignment tables exist for each test."""


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for an org_admin user linked to the seeded organization."""
    with Session(sync_engine) as session:
        if session.get(User, ORG_ADMIN_ID) is None:
            session.add(
                User(
                    id=ORG_ADMIN_ID,
                    email="orgadmin.assignments@test.com",
                    username="orgadminassign",
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
def assignment_context(org_admin_headers: dict[str, str], client: TestClient) -> dict[str, str | UUID]:
    """Seed coach, team, and practice plan used for assignment tests."""
    with sync_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO coaches (id, org_id, first_name, last_name, email)
                VALUES (:id, :org_id, 'Taylor', 'Reed', 'coach.assign@test.com')
                ON CONFLICT (id) DO UPDATE SET
                    org_id = EXCLUDED.org_id,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    email = EXCLUDED.email
                """
            ),
            {"id": SEEDED_COACH_ID, "org_id": SEEDED_ORG_ID},
        )
        connection.execute(
            text(
                """
                INSERT INTO teams (id, org_id, name, team_view_code, level)
                VALUES (:id, :org_id, 'Varsity Boys', 'VB-ASSIGN', '16-18')
                ON CONFLICT (id) DO UPDATE SET
                    org_id = EXCLUDED.org_id,
                    name = EXCLUDED.name,
                    team_view_code = EXCLUDED.team_view_code,
                    level = EXCLUDED.level
                """
            ),
            {"id": SEEDED_TEAM_ID, "org_id": SEEDED_ORG_ID},
        )
        connection.execute(text("DELETE FROM practice_plan_drills"))
        connection.execute(text("DELETE FROM practice_plans"))
        connection.execute(
            text(
                """
                INSERT INTO practice_plans (
                    id, name, org_id, created_by_user, created_by_name,
                    drill_count, description, active
                )
                VALUES (
                    :id, 'Shooting Fundamentals', :org_id, :admin_id, 'Org Admin',
                    2, 'Weekly shooting progression', true
                )
                """
            ),
            {"id": SEEDED_PLAN_ID, "org_id": SEEDED_ORG_ID, "admin_id": ORG_ADMIN_ID},
        )
        connection.execute(
            text(
                """
                INSERT INTO practice_plan_drills (
                    id, plan_id, drill_id, drill_name, order_num
                )
                VALUES
                    ('00000000-0000-4000-8000-000000000084', :plan_id, :drill_one, 'Spot Up', 0),
                    ('00000000-0000-4000-8000-000000000085', :plan_id, :drill_two, 'Free Throw Line', 1)
                """
            ),
            {
                "plan_id": SEEDED_PLAN_ID,
                "drill_one": "00000000-0000-4000-8000-000000000041",
                "drill_two": "00000000-0000-4000-8000-000000000042",
            },
        )

    return {
        "coach_id": SEEDED_COACH_ID,
        "team_id": SEEDED_TEAM_ID,
        "plan_id": SEEDED_PLAN_ID,
    }


def _valid_assign_payload(context: dict[str, str | UUID]) -> dict[str, str]:
    return {
        "coach_id": str(context["coach_id"]),
        "team_id": str(context["team_id"]),
        "plan_id": str(context["plan_id"]),
        "start_date": "2026-09-01",
        "frequency": "Every Tuesday & Thursday",
        "phone": "+1-555-0100",
    }


def test_assign_practice_plan_201(
    client: TestClient,
    org_admin_headers: dict[str, str],
    assignment_context: dict[str, str | UUID],
) -> None:
    response = client.post(
        ASSIGN_URL,
        headers=org_admin_headers,
        json=_valid_assign_payload(assignment_context),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "assigned"
    assert body["title"] == "Shooting Fundamentals"
    assert body["name"] == "Shooting Fundamentals"
    assert body["organization"]
    assert body["coach_id"] == str(SEEDED_COACH_ID)
    assert body["plan_id"] == str(SEEDED_PLAN_ID)
    assert body["frequency"] == "Every Tuesday & Thursday"
    assert body["drill_count"] == 2


def test_assign_practice_plan_400_missing_required_fields(
    client: TestClient,
    org_admin_headers: dict[str, str],
    assignment_context: dict[str, str | UUID],
) -> None:
    response = client.post(
        ASSIGN_URL,
        headers=org_admin_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_assign_practice_plan_409_duplicate_assignment(
    client: TestClient,
    org_admin_headers: dict[str, str],
    assignment_context: dict[str, str | UUID],
) -> None:
    payload = _valid_assign_payload(assignment_context)
    first = client.post(ASSIGN_URL, headers=org_admin_headers, json=payload)
    assert first.status_code == 201

    duplicate = client.post(ASSIGN_URL, headers=org_admin_headers, json=payload)
    assert duplicate.status_code == 409
    body = duplicate.json()
    assert body["success"] is False
    assert body["error"]["code"] == "PRACTICE_PLAN_ALREADY_ASSIGNED"


def test_list_practice_plan_assignments_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    assignment_context: dict[str, str | UUID],
) -> None:
    create = client.post(
        ASSIGN_URL,
        headers=org_admin_headers,
        json=_valid_assign_payload(assignment_context),
    )
    assert create.status_code == 201

    response = client.get(PRACTICE_PLANS_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["organization"]
    assert len(body["plans"]) >= 1
    assert len(body["assignments"]) == 1
    assignment = body["assignments"][0]
    assert assignment["title"] == "Shooting Fundamentals"
    assert assignment["coach_name"] == "Taylor Reed"
    assert assignment["team_name"] == "Varsity Boys"
    assert assignment["frequency"] == "Every Tuesday & Thursday"
    assert assignment["status"] == "assigned"


def test_update_practice_plan_assignment_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    assignment_context: dict[str, str | UUID],
) -> None:
    create = client.post(
        ASSIGN_URL,
        headers=org_admin_headers,
        json=_valid_assign_payload(assignment_context),
    )
    assert create.status_code == 201
    assignment_id = create.json()["id"]

    response = client.put(
        f"{PRACTICE_PLANS_BASE}/{assignment_id}",
        headers=org_admin_headers,
        json={
            "start_date": "2026-09-15",
            "frequency": "Every Monday & Wednesday",
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["start_date"] == "2026-09-15"
    assert body["frequency"] == "Every Monday & Wednesday"
    assert body["message"] == "Practice plan assignment updated successfully"
