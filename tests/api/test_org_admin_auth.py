"""Integration tests for organization admin login API (HE-423)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from tests.conftest import (
    ORG_ADMIN_LOGIN_BASE,
    REGULAR_EMAIL,
    REGULAR_PASSWORD,
    SEEDED_ORG_ID,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000055")
ORG_ADMIN_EMAIL = "orgadmin.login@test.com"
ORG_ADMIN_PASSWORD = "OrgAdmin123!"
ORG_ADMIN_USERNAME = "orgadminlogin"


@pytest.fixture
def org_admin_user(seeded_users: dict) -> None:
    """Seed an organization admin account for login tests."""
    with Session(sync_engine) as session:
        existing = session.get(User, ORG_ADMIN_ID)
        if existing is None:
            session.add(
                User(
                    id=ORG_ADMIN_ID,
                    email=ORG_ADMIN_EMAIL,
                    username=ORG_ADMIN_USERNAME,
                    encrypted_password=hash_password(ORG_ADMIN_PASSWORD),
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


def _login_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "email": ORG_ADMIN_EMAIL,
        "username": ORG_ADMIN_EMAIL,
        "password": ORG_ADMIN_PASSWORD,
        "phone": "+1-555-0100",
        "remember_me": False,
    }
    payload.update(overrides)
    return payload


def test_org_admin_login_success_200(
    client: TestClient,
    org_admin_user: None,
) -> None:
    response = client.post(ORG_ADMIN_LOGIN_BASE, json=_login_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Login successful! Redirecting to dashboard..."
    assert body["title"] == "LOGIN"
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in_hours"] == settings.ACCESS_TOKEN_EXPIRE_HOURS
    assert body["email"] == ORG_ADMIN_EMAIL
    assert body["username"] == ORG_ADMIN_USERNAME
    assert body["id"] == str(ORG_ADMIN_ID)
    assert body["organization"] == "Seeded Hoops Club"
    assert body["link"].endswith("/organization/dashboard")
    assert body["password"] is None
    assert body["error"] is None
    assert body["user"]["role"] == "org_admin"


def test_org_admin_login_by_username_200(
    client: TestClient,
    org_admin_user: None,
) -> None:
    response = client.post(
        ORG_ADMIN_LOGIN_BASE,
        json=_login_payload(email=None, username=ORG_ADMIN_USERNAME),
    )
    assert response.status_code == 200
    assert response.json()["username"] == ORG_ADMIN_USERNAME


def test_org_admin_login_invalid_credentials_401(
    client: TestClient,
    org_admin_user: None,
) -> None:
    response = client.post(
        ORG_ADMIN_LOGIN_BASE,
        json=_login_payload(password="WrongPassword123!"),
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "INVALID_CREDENTIALS"
    assert "Invalid username or password" in body["error"]["message"]


def test_org_admin_login_empty_username_400(client: TestClient) -> None:
    response = client.post(
        ORG_ADMIN_LOGIN_BASE,
        json=_login_payload(email="", username=""),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "username"


def test_org_admin_login_empty_password_400(
    client: TestClient,
    org_admin_user: None,
) -> None:
    response = client.post(
        ORG_ADMIN_LOGIN_BASE,
        json=_login_payload(password=""),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "password"


def test_org_admin_login_invalid_email_format_400(client: TestClient) -> None:
    response = client.post(
        ORG_ADMIN_LOGIN_BASE,
        json=_login_payload(email="not-an-email", username="not-an-email"),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"


def test_org_admin_login_weak_password_400(client: TestClient) -> None:
    response = client.post(
        ORG_ADMIN_LOGIN_BASE,
        json=_login_payload(password="short"),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "password"


def test_org_admin_login_coach_credentials_401(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        ORG_ADMIN_LOGIN_BASE,
        json=_login_payload(email=REGULAR_EMAIL, username=REGULAR_EMAIL, password=REGULAR_PASSWORD),
    )
    assert response.status_code == 401
