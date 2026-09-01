"""Integration tests for organization admin change password API (HE-406, HE-410)."""

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
    ORG_ADMIN_CHANGE_PASSWORD_BASE,
    ORG_CHANGE_PASSWORD_BASE,
    REGULAR_USER_ID,
    SEEDED_ORG_ID,
    TEST_DIFFERENT_PASSWORD,
    TEST_INVALID_PASSWORD,
    TEST_NEW_SECURE_PASSWORD,
    TEST_VALID_PASSWORD,
    TEST_WEAK_PASSWORD,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000051")
ORG_ADMIN_PASSWORD = TEST_VALID_PASSWORD


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for an org_admin user linked to the seeded organization."""
    with Session(sync_engine) as session:
        existing = session.get(User, ORG_ADMIN_ID)
        if existing is None:
            session.add(
                User(
                    id=ORG_ADMIN_ID,
                    email="orgadmin.profile@test.com",
                    username="orgadminprofile",
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
    return auth_headers(create_access_token(ORG_ADMIN_ID))


def _change_password_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "current_password": ORG_ADMIN_PASSWORD,
        "new_password": TEST_NEW_SECURE_PASSWORD,
        "confirm_password": TEST_NEW_SECURE_PASSWORD,
        "phone": "+1-555-0100",
        "password": TEST_NEW_SECURE_PASSWORD,
    }
    payload.update(overrides)
    return payload


def _restore_org_admin_password() -> None:
    with Session(sync_engine) as session:
        user = session.get(User, ORG_ADMIN_ID)
        assert user is not None
        user.encrypted_password = hash_password(ORG_ADMIN_PASSWORD)
        session.commit()


def test_change_password_success_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    try:
        response = client.post(
            ORG_CHANGE_PASSWORD_BASE,
            headers=org_admin_headers,
            json=_change_password_payload(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["status"] == "password_changed"
        assert body["message"] == "Password changed successfully"
        assert body["description"]
        assert body["error"] is None
        assert body["password"] is None
        assert body["phone"] == "+1-555-0100"
        assert body["id"] == str(ORG_ADMIN_ID)
    finally:
        _restore_org_admin_password()


def test_change_password_wrong_current_400(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        ORG_CHANGE_PASSWORD_BASE,
        headers=org_admin_headers,
        json=_change_password_payload(current_password=TEST_INVALID_PASSWORD),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "current_password"


def test_change_password_weak_400(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        ORG_CHANGE_PASSWORD_BASE,
        headers=org_admin_headers,
        json=_change_password_payload(
            new_password=TEST_WEAK_PASSWORD,
            confirm_password=TEST_WEAK_PASSWORD,
            password=TEST_WEAK_PASSWORD,
        ),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_change_password_mismatch_400(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        ORG_CHANGE_PASSWORD_BASE,
        headers=org_admin_headers,
        json=_change_password_payload(
            confirm_password=TEST_DIFFERENT_PASSWORD,
            password=TEST_DIFFERENT_PASSWORD,
        ),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "confirm_password"


def test_change_password_empty_fields_400(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        ORG_CHANGE_PASSWORD_BASE,
        headers=org_admin_headers,
        json={
            "current_password": "",
            "new_password": "",
            "confirm_password": "",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_change_password_forbidden_coach_403(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        ORG_CHANGE_PASSWORD_BASE,
        headers=coach_headers,
        json=_change_password_payload(),
    )
    assert response.status_code == 403


@pytest.fixture
def coach_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for a coach user (non org-admin)."""
    return auth_headers(create_access_token(REGULAR_USER_ID))


def test_admin_alias_change_password_success_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    try:
        response = client.post(
            ORG_ADMIN_CHANGE_PASSWORD_BASE,
            headers=org_admin_headers,
            json=_change_password_payload(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["status"] == "password_changed"
        assert body["message"] == "Password changed successfully"
        assert body["description"]
        assert body["error"] is None
        assert body["password"] is None
        assert body["phone"] == "+1-555-0100"
        assert body["id"] == str(ORG_ADMIN_ID)
    finally:
        _restore_org_admin_password()


def test_admin_alias_change_password_wrong_current_400(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        ORG_ADMIN_CHANGE_PASSWORD_BASE,
        headers=org_admin_headers,
        json=_change_password_payload(current_password=TEST_INVALID_PASSWORD),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "current_password"


def test_admin_alias_change_password_weak_400(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        ORG_ADMIN_CHANGE_PASSWORD_BASE,
        headers=org_admin_headers,
        json=_change_password_payload(
            new_password=TEST_WEAK_PASSWORD,
            confirm_password=TEST_WEAK_PASSWORD,
            password=TEST_WEAK_PASSWORD,
        ),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_admin_alias_change_password_mismatch_400(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        ORG_ADMIN_CHANGE_PASSWORD_BASE,
        headers=org_admin_headers,
        json=_change_password_payload(
            confirm_password=TEST_DIFFERENT_PASSWORD,
            password=TEST_DIFFERENT_PASSWORD,
        ),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "confirm_password"


def test_admin_alias_change_password_forbidden_coach_403(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        ORG_ADMIN_CHANGE_PASSWORD_BASE,
        headers=coach_headers,
        json=_change_password_payload(),
    )
    assert response.status_code == 403
