"""Integration tests for organization admin reset password API (HE-398)."""

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
    ORG_ADMIN_RESET_PASSWORD_BASE,
    ORG_ADMIN_RESET_PASSWORD_VALIDATE_BASE,
    SEEDED_ORG_ID,
    TEST_DIFFERENT_PASSWORD,
    TEST_NEW_PASSWORD,
    TEST_VALID_PASSWORD,
    TEST_WEAK_PASSWORD,
    TEST_WEAK_PASSWORD_LONG,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000095")


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for an org_admin user linked to the seeded organization."""
    with Session(sync_engine) as session:
        if session.get(User, ORG_ADMIN_ID) is None:
            session.add(
                User(
                    id=ORG_ADMIN_ID,
                    email="orgadmin.reset@test.com",
                    username="orgadminreset",
                    encrypted_password=hash_password(TEST_VALID_PASSWORD),
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


def _reset_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "new_password": TEST_NEW_PASSWORD,
        "confirm_password": TEST_NEW_PASSWORD,
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


def _restore_org_admin_password() -> None:
    with Session(sync_engine) as session:
        user = session.get(User, ORG_ADMIN_ID)
        assert user is not None
        user.encrypted_password = hash_password(TEST_VALID_PASSWORD)
        session.commit()


def test_reset_org_admin_password_success_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    try:
        response = client.post(
            ORG_ADMIN_RESET_PASSWORD_BASE,
            headers=org_admin_headers,
            json=_reset_payload(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["status"] == "password_reset"
        assert body["message"] == "Password has been reset successfully."
        assert body["description"]
        assert body["link"]
        assert body["error"] is None
        assert body["password"] is None
        assert body["id"] == str(ORG_ADMIN_ID)
    finally:
        _restore_org_admin_password()


def test_reset_org_admin_password_mismatch_400(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        ORG_ADMIN_RESET_PASSWORD_BASE,
        headers=org_admin_headers,
        json=_reset_payload(confirm_password=TEST_DIFFERENT_PASSWORD),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "confirm_password"


def test_reset_org_admin_password_weak_400(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        ORG_ADMIN_RESET_PASSWORD_BASE,
        headers=org_admin_headers,
        json=_reset_payload(new_password=TEST_WEAK_PASSWORD, confirm_password=TEST_WEAK_PASSWORD),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_reset_org_admin_password_empty_fields_400(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        ORG_ADMIN_RESET_PASSWORD_BASE,
        headers=org_admin_headers,
        json={"new_password": "", "confirm_password": ""},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "new_password"


def test_reset_org_admin_password_too_short_400(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    short = "Ab1!"
    response = client.post(
        ORG_ADMIN_RESET_PASSWORD_BASE,
        headers=org_admin_headers,
        json=_reset_payload(new_password=short, confirm_password=short),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "8 characters" in body["error"]["message"]


def test_reset_org_admin_password_missing_uppercase_400(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    weak = "password123!"
    response = client.post(
        ORG_ADMIN_RESET_PASSWORD_BASE,
        headers=org_admin_headers,
        json=_reset_payload(new_password=weak, confirm_password=weak),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "uppercase" in body["error"]["message"].lower()


def test_reset_org_admin_password_missing_number_400(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    weak = "Password!!!!"
    response = client.post(
        ORG_ADMIN_RESET_PASSWORD_BASE,
        headers=org_admin_headers,
        json=_reset_payload(new_password=weak, confirm_password=weak),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "number" in body["error"]["message"].lower()


def test_reset_org_admin_password_missing_special_400(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    weak = "Password1234"
    response = client.post(
        ORG_ADMIN_RESET_PASSWORD_BASE,
        headers=org_admin_headers,
        json=_reset_payload(new_password=weak, confirm_password=weak),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "special" in body["error"]["message"].lower()


def test_reset_org_admin_password_same_as_current_409(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        ORG_ADMIN_RESET_PASSWORD_BASE,
        headers=org_admin_headers,
        json=_reset_payload(
            new_password=TEST_VALID_PASSWORD,
            confirm_password=TEST_VALID_PASSWORD,
        ),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PASSWORD_UNCHANGED"


def test_reset_org_admin_password_forbidden_coach_403(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        ORG_ADMIN_RESET_PASSWORD_BASE,
        headers=coach_headers,
        json=_reset_payload(),
    )
    assert response.status_code == 403


def test_validate_org_admin_password_strength_valid_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.get(
        ORG_ADMIN_RESET_PASSWORD_VALIDATE_BASE,
        headers=org_admin_headers,
        params={"password": TEST_NEW_PASSWORD, "phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "valid"
    assert body["message"] == "Password meets all strength requirements."
    assert body["strength"] == "strong"
    assert body["requirements"]["min_length"] is True
    assert body["requirements"]["has_number"] is True
    assert body["requirements"]["has_special"] is True
    assert body["requirements"]["has_uppercase"] is True
    assert body["error"] is None
    assert body["password"] is None
    assert body["phone"] == "+1-555-0100"


def test_validate_org_admin_password_strength_invalid_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.get(
        ORG_ADMIN_RESET_PASSWORD_VALIDATE_BASE,
        headers=org_admin_headers,
        params={"password": TEST_WEAK_PASSWORD_LONG},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "invalid"
    assert body["message"] == "Password does not meet all strength requirements."
    assert body["requirements"]["has_uppercase"] is False
    assert body["requirements"]["has_special"] is False


def test_validate_org_admin_password_strength_empty_400(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    response = client.get(
        ORG_ADMIN_RESET_PASSWORD_VALIDATE_BASE,
        headers=org_admin_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_validate_org_admin_password_strength_forbidden_coach_403(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(
        ORG_ADMIN_RESET_PASSWORD_VALIDATE_BASE,
        headers=coach_headers,
        params={"password": TEST_NEW_PASSWORD},
    )
    assert response.status_code == 403
