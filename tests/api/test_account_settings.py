"""Integration tests for Account Settings API (HE-316)."""

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
    ADMIN_EMAIL,
    REGULAR_EMAIL,
    REGULAR_PASSWORD,
    REGULAR_USER_ID,
    SEEDED_ORG_ID,
    TEST_NEW_PASSWORD,
    sync_engine,
)

ACCOUNT_SETTINGS_BASE = "/api/v1/account/settings"
CHANGE_PASSWORD_URL = f"{ACCOUNT_SETTINGS_BASE}/change-password"
ORGANIZATION_URL = f"{ACCOUNT_SETTINGS_BASE}/organization"
AUTH_KEYS_URL = f"{ACCOUNT_SETTINGS_BASE}/authentication-keys"
PUSH_URL = f"{ACCOUNT_SETTINGS_BASE}/push-notifications"
HELP_SUPPORT_URL = f"{ACCOUNT_SETTINGS_BASE}/help-support"
PROFILE_URL = f"{ACCOUNT_SETTINGS_BASE}/profile"
SUPPORT_CONTACT_URL = f"{ACCOUNT_SETTINGS_BASE}/help-support/contact"

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000040")
OTHER_ORG_ID = UUID("00000000-0000-4000-8000-000000000011")


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for an org_admin user."""
    with Session(sync_engine) as session:
        existing = session.get(User, ORG_ADMIN_ID)
        if existing is None:
            org_admin = User(
                id=ORG_ADMIN_ID,
                email="orgadmin@test.com",
                username="orgadmin",
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
    from tests.conftest import auth_headers, create_access_token

    return auth_headers(create_access_token(ORG_ADMIN_ID))


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


def _change_password_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "current_password": REGULAR_PASSWORD,
        "new_password": TEST_NEW_PASSWORD,
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


def _restore_regular_password() -> None:
    with Session(sync_engine) as session:
        user = session.get(User, REGULAR_USER_ID)
        assert user is not None
        user.encrypted_password = hash_password(REGULAR_PASSWORD)
        session.commit()


def test_change_password_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    try:
        response = client.post(
            CHANGE_PASSWORD_URL,
            headers=coach_headers,
            json=_change_password_payload(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["message"] == "Password changed successfully"
        assert body["status"] == "password_changed"
        assert body["error"] is None
        assert body["password"] is None
        assert body["id"] == str(REGULAR_USER_ID)
    finally:
        _restore_regular_password()


def test_change_password_empty_current_400(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        CHANGE_PASSWORD_URL,
        headers=coach_headers,
        json=_change_password_payload(current_password=""),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_change_password_weak_400(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        CHANGE_PASSWORD_URL,
        headers=coach_headers,
        json=_change_password_payload(new_password="weakpass"),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_organization_duplicate_409(
    client: TestClient,
    coach_headers: dict[str, str],
    duplicate_org: None,
) -> None:
    response = client.put(
        ORGANIZATION_URL,
        headers=coach_headers,
        json={"organization_name": "Duplicate Org Name", "phone": "+1-555-0100"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORGANIZATION_NAME_EXISTS"


def test_update_organization_success_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.put(
        ORGANIZATION_URL,
        headers=coach_headers,
        json={"organization_name": "Updated Hoops Club", "phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["organization_name"] == "Updated Hoops Club"


def test_update_auth_keys_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.put(
        AUTH_KEYS_URL,
        headers=coach_headers,
        json={
            "auth_keys": {"key1": "alpha-key", "key2": "beta-key"},
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["auth_keys"]["key1"] == "alpha-key"
    assert body["auth_keys"]["key2"] == "beta-key"


def test_enable_push_notifications_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.patch(
        PUSH_URL,
        headers=org_admin_headers,
        json={"push_notifications_enabled": True, "phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["push_notifications_enabled"] is True


def test_enable_push_notifications_unauthorized_400(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.patch(
        PUSH_URL,
        headers=coach_headers,
        json={"push_notifications_enabled": True, "phone": "+1-555-0100"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_get_help_support_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(HELP_SUPPORT_URL, headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["title"] == "Help & Support"
    assert len(body["articles"]) >= 1
    assert "question" in body["articles"][0]
    assert "answer" in body["articles"][0]
    assert body["profile"]["full_name"]
    assert body["profile"]["role"] == "coach"


def test_submit_support_valid_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        SUPPORT_CONTACT_URL,
        headers=coach_headers,
        json={
            "email": REGULAR_EMAIL,
            "phone": "+15558392001",
            "inquiry_subject": "Technical Issue",
            "message_description": "Need help with my account settings.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "submitted"
    assert body["request_id"]


def test_submit_support_invalid_400(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        SUPPORT_CONTACT_URL,
        headers=coach_headers,
        json={
            "email": "not-an-email",
            "phone": "+15558392001",
            "inquiry_subject": "Technical Issue",
            "message_description": "Help please",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_submit_support_invalid_subject_409(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        SUPPORT_CONTACT_URL,
        headers=coach_headers,
        json={
            "email": REGULAR_EMAIL,
            "phone": "+15558392001",
            "inquiry_subject": "Random Topic",
            "message_description": "Help please",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_INQUIRY_SUBJECT"


def test_update_profile_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.put(
        PROFILE_URL,
        headers=coach_headers,
        json={
            "full_name": "Jane Doe",
            "email": REGULAR_EMAIL,
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["name"] == "Jane Doe"
    assert body["first_name"] == "Jane"
    assert body["last_name"] == "Doe"
    assert body["profile"]["email"] == REGULAR_EMAIL


def test_update_profile_missing_fields_422(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.put(
        PROFILE_URL,
        headers=coach_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_profile_duplicate_email_409(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.put(
        PROFILE_URL,
        headers=coach_headers,
        json={
            "full_name": "Jane Doe",
            "email": ADMIN_EMAIL,
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_IN_USE"


def test_account_settings_unauthenticated_403(client: TestClient) -> None:
    response = client.get(HELP_SUPPORT_URL)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
