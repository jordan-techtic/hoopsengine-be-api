"""Integration tests for coach login and forgot-password (HE-459)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from tests.conftest import (
    COACH_FORGOT_PASSWORD_BASE,
    COACH_LOGIN_BASE,
    REGULAR_EMAIL,
    REGULAR_PASSWORD,
    TEST_INVALID_PASSWORD,
    UNVERIFIED_COACH_EMAIL,
    UNVERIFIED_COACH_PASSWORD,
)


def _login_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "email": REGULAR_EMAIL,
        "password": REGULAR_PASSWORD,
        "remember_me": False,
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


def test_coach_login_valid_credentials_200_jwt(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(COACH_LOGIN_BASE, json=_login_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Login successful"
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in_hours"] == settings.ACCESS_TOKEN_EXPIRE_HOURS
    assert body["user"]["email"] == REGULAR_EMAIL
    assert body["user"]["username"] == "regularcoach"
    assert body["error"] is None


def test_coach_login_by_username_200(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        COACH_LOGIN_BASE,
        json=_login_payload(email="regularcoach"),
    )
    assert response.status_code == 200
    assert response.json()["user"]["username"] == "regularcoach"


def test_coach_login_invalid_credentials_401(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        COACH_LOGIN_BASE,
        json=_login_payload(password=TEST_INVALID_PASSWORD),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_coach_login_empty_password_400(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        COACH_LOGIN_BASE,
        json=_login_payload(password="   "),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "password"


def test_coach_login_missing_email_422(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        COACH_LOGIN_BASE,
        json={"password": REGULAR_PASSWORD},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["loc"][-1] == "email"


def test_coach_login_missing_password_422(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        COACH_LOGIN_BASE,
        json={"email": REGULAR_EMAIL},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["loc"][-1] == "password"


def test_coach_login_unverified_email_401(
    client: TestClient,
    unverified_coach_user: object,
) -> None:
    response = client.post(
        COACH_LOGIN_BASE,
        json={
            "email": UNVERIFIED_COACH_EMAIL,
            "password": UNVERIFIED_COACH_PASSWORD,
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_coach_login_remember_me_longer_expiry(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        COACH_LOGIN_BASE,
        json=_login_payload(remember_me=True),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["remember_me"] is True
    assert body["expires_in_hours"] == settings.REMEMBER_ME_TOKEN_EXPIRE_HOURS


def test_coach_forgot_password_success(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        COACH_FORGOT_PASSWORD_BASE,
        json={"email": REGULAR_EMAIL, "phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "reset" in body["message"].lower()
    assert body["link"] == settings.RESET_PASSWORD_URL
    assert body["status"] == "reset_email_sent"


def test_coach_forgot_password_unknown_email_404(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        COACH_FORGOT_PASSWORD_BASE,
        json={"email": "unknown@example.com"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"

def test_coach_login_success_message_he459(
    client: TestClient,
    seeded_users: dict,
) -> None:
    """HE-459: valid credentials return 200 with success message."""
    response = client.post(COACH_LOGIN_BASE, json=_login_payload())
    assert response.status_code == 200
    assert response.json()["message"] == "Login successful"


def test_coach_login_invalid_username_401(
    client: TestClient,
    seeded_users: dict,
) -> None:
    """HE-459: invalid email/username returns 401."""
    response = client.post(
        COACH_LOGIN_BASE,
        json=_login_payload(email="nobody@example.com", password=REGULAR_PASSWORD),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_coach_forgot_password_link_he459(
    client: TestClient,
    seeded_users: dict,
) -> None:
    """HE-459: forgot-password response includes reset page link for FE."""
    response = client.post(
        COACH_FORGOT_PASSWORD_BASE,
        json={"email": REGULAR_EMAIL},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["link"] == settings.RESET_PASSWORD_URL
    assert body["link"].endswith("reset-password") or "reset-password" in body["link"]
