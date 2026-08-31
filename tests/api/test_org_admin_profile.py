"""Integration tests for organization admin profile API (HE-385)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.organization import Organization
from app.models.user import User
from tests.conftest import (
    REGULAR_USER_ID,
    SEEDED_ORG_ID,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORGANIZATION_PROFILE_BASE = "/api/v1/organization/profile"
ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000051")
OTHER_ORG_ID = UUID("00000000-0000-4000-8000-000000000011")

VALID_PROFILE_PAYLOAD = {
    "organization_name": "Courtside Elite Academy",
    "address": "1234 Basketball Ave",
    "email": "org.profile@test.com",
    "phone_number": "+1 (555) 382-9102",
    "first_name": "Jane",
    "last_name": "Doe",
    "phone": "+1-555-0100",
}

MANAGEMENT_PROFILE_PAYLOAD = {
    "name": "Elite Basketball Organization",
    "description": "Premier youth basketball development organization",
    "contact_info": "elite.contact@test.com",
}

ORG_ADMIN_NO_ORG_ID = UUID("00000000-0000-4000-8000-000000000052")


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for an org_admin user linked to the seeded organization."""
    with Session(sync_engine) as session:
        existing = session.get(User, ORG_ADMIN_ID)
        if existing is None:
            org_admin = User(
                id=ORG_ADMIN_ID,
                email="orgadmin.profile@test.com",
                username="orgadminprofile",
                encrypted_password=hash_password("OrgAdmin123!"),
                role=UserRole.ORG_ADMIN.value,
                first_name="Org",
                last_name="Admin",
                is_super_admin=False,
                is_active=True,
                org_id=SEEDED_ORG_ID,
                email_confirmed_at=datetime.now(timezone.utc),
            )
            session.add(org_admin)
            session.commit()
    return auth_headers(create_access_token(ORG_ADMIN_ID))


@pytest.fixture
def coach_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for a coach user (non org-admin)."""
    return auth_headers(create_access_token(REGULAR_USER_ID))


@pytest.fixture
def duplicate_org(seeded_users: dict) -> None:
    """Seed a second organization for duplicate-name tests."""
    with Session(sync_engine) as session:
        if session.get(Organization, OTHER_ORG_ID) is None:
            session.add(
                Organization(
                    id=OTHER_ORG_ID,
                    name="Duplicate Org Name",
                    admin_email="duplicate@test.com",
                    phone_number="5559990000",
                    address="2 Court Ave",
                    join_code="DUPORG01",
                )
            )
            session.commit()


def test_get_organization_profile_200(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    response = client.get(ORGANIZATION_PROFILE_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["id"] == str(SEEDED_ORG_ID)
    assert body["organization_name"] == "Seeded Hoops Club"
    assert body["address"] == "1 Court Ave"
    assert body["email"] == "seeded-org@test.com"
    assert body["full_name"] == "Org Admin"
    assert body["role"] == UserRole.ORG_ADMIN.value
    assert body["profile"]["organization_name"] == "Seeded Hoops Club"
    assert body["profile"]["full_name"] == "Org Admin"
    assert body["profile"]["role"] == UserRole.ORG_ADMIN.value
    assert body["error"] is None


def test_update_organization_profile_200(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    response = client.put(
        ORGANIZATION_PROFILE_BASE,
        json=VALID_PROFILE_PAYLOAD,
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Organization profile updated successfully"
    assert body["status"] == "saved"
    assert body["organization_name"] == VALID_PROFILE_PAYLOAD["organization_name"]
    assert body["address"] == VALID_PROFILE_PAYLOAD["address"]
    assert body["email"] == VALID_PROFILE_PAYLOAD["email"]
    assert body["first_name"] == "Jane"
    assert body["last_name"] == "Doe"


def test_update_missing_organization_name_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    payload = dict(VALID_PROFILE_PAYLOAD)
    payload["organization_name"] = ""
    response = client.put(ORGANIZATION_PROFILE_BASE, json=payload, headers=org_admin_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_missing_email_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    payload = dict(VALID_PROFILE_PAYLOAD)
    payload["email"] = ""
    response = client.put(ORGANIZATION_PROFILE_BASE, json=payload, headers=org_admin_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_duplicate_organization_name_409(
    org_admin_headers: dict[str, str],
    client: TestClient,
    duplicate_org: None,
) -> None:
    payload = dict(VALID_PROFILE_PAYLOAD)
    payload["organization_name"] = "Duplicate Org Name"
    response = client.put(ORGANIZATION_PROFILE_BASE, json=payload, headers=org_admin_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORGANIZATION_NAME_EXISTS"


def test_update_invalid_email_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    payload = dict(VALID_PROFILE_PAYLOAD)
    payload["email"] = "not-an-email"
    response = client.put(ORGANIZATION_PROFILE_BASE, json=payload, headers=org_admin_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_missing_first_name_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    payload = dict(VALID_PROFILE_PAYLOAD)
    payload["first_name"] = ""
    response = client.put(ORGANIZATION_PROFILE_BASE, json=payload, headers=org_admin_headers)
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "first_name"


def test_update_missing_last_name_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    payload = dict(VALID_PROFILE_PAYLOAD)
    payload["last_name"] = "   "
    response = client.put(ORGANIZATION_PROFILE_BASE, json=payload, headers=org_admin_headers)
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "last_name"


def test_organization_profile_forbidden_coach_403(
    coach_headers: dict[str, str],
    client: TestClient,
) -> None:
    response = client.get(ORGANIZATION_PROFILE_BASE, headers=coach_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_get_organization_profile_management_fields_200(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    """Organization Profile Management: GET returns name, description, and contact_info."""
    client.put(
        ORGANIZATION_PROFILE_BASE,
        json=MANAGEMENT_PROFILE_PAYLOAD,
        headers=org_admin_headers,
    )
    response = client.get(ORGANIZATION_PROFILE_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["name"] == MANAGEMENT_PROFILE_PAYLOAD["name"]
    assert body["organization_description"] == MANAGEMENT_PROFILE_PAYLOAD["description"]
    assert body["contact_info"] == MANAGEMENT_PROFILE_PAYLOAD["contact_info"]
    assert body["profile"]["organization_description"] == MANAGEMENT_PROFILE_PAYLOAD["description"]
    assert body["profile"]["contact_info"] == MANAGEMENT_PROFILE_PAYLOAD["contact_info"]


def test_update_organization_profile_management_200(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    response = client.put(
        ORGANIZATION_PROFILE_BASE,
        json=MANAGEMENT_PROFILE_PAYLOAD,
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Organization profile updated successfully"
    assert body["description"] == "Your organization details have been saved"
    assert body["name"] == MANAGEMENT_PROFILE_PAYLOAD["name"]
    assert body["organization_description"] == MANAGEMENT_PROFILE_PAYLOAD["description"]
    assert body["contact_info"] == MANAGEMENT_PROFILE_PAYLOAD["contact_info"]


def test_update_management_missing_name_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    payload = dict(MANAGEMENT_PROFILE_PAYLOAD)
    payload["name"] = ""
    response = client.put(ORGANIZATION_PROFILE_BASE, json=payload, headers=org_admin_headers)
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "name"


def test_update_management_missing_description_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    payload = dict(MANAGEMENT_PROFILE_PAYLOAD)
    payload["description"] = "   "
    response = client.put(ORGANIZATION_PROFILE_BASE, json=payload, headers=org_admin_headers)
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "description"


def test_update_management_invalid_contact_info_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    payload = dict(MANAGEMENT_PROFILE_PAYLOAD)
    payload["contact_info"] = "not-a-valid-contact"
    response = client.put(ORGANIZATION_PROFILE_BASE, json=payload, headers=org_admin_headers)
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "contact_info"


def test_get_organization_profile_404_no_org(
    seeded_users: dict,
    client: TestClient,
) -> None:
    with Session(sync_engine) as session:
        existing = session.get(User, ORG_ADMIN_NO_ORG_ID)
        if existing is None:
            session.add(
                User(
                    id=ORG_ADMIN_NO_ORG_ID,
                    email="orgadmin.noorg@test.com",
                    username="orgadminnoorg",
                    encrypted_password=hash_password("OrgAdmin123!"),
                    role=UserRole.ORG_ADMIN.value,
                    first_name="No",
                    last_name="Org",
                    is_super_admin=False,
                    is_active=True,
                    org_id=None,
                    email_confirmed_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
    headers = auth_headers(create_access_token(ORG_ADMIN_NO_ORG_ID))
    response = client.get(ORGANIZATION_PROFILE_BASE, headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORGANIZATION_NOT_FOUND"
