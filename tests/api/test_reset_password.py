"""Integration tests for authenticated reset password endpoints (HE-298)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from tests.conftest import (
    REGULAR_PASSWORD,
    REGULAR_USER_ID,
    TEST_NEW_PASSWORD,
    TEST_WEAK_PASSWORD,
    TEST_WEAK_PASSWORD_LONG,
    TEST_DIFFERENT_PASSWORD,
    sync_engine,
)

from tests.conftest import RESET_PASSWORD_BASE, VALIDATE_PASSWORD_BASE


def _reset_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "new_password": TEST_NEW_PASSWORD,
        "confirm_password": TEST_NEW_PASSWORD,
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


def test_reset_password_success_201(
    client: TestClient,
    user_headers: dict[str, str],
) -> None:
    try:
        response = client.post(
            RESET_PASSWORD_BASE,
            headers=user_headers,
            json=_reset_payload(),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["status"] == "password_reset"
        assert body["message"]
        assert body["description"]
        assert body["link"]
        assert body["error"] is None
        assert body["password"] is None
        assert body["id"] == str(REGULAR_USER_ID)
    finally:
        _restore_regular_password()


def test_reset_password_unauthorized_403(client: TestClient) -> None:
    response = client.post(RESET_PASSWORD_BASE, json=_reset_payload())
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "FORBIDDEN"


def test_reset_password_weak_password_400(
    client: TestClient,
    user_headers: dict[str, str],
) -> None:
    response = client.post(
        RESET_PASSWORD_BASE,
        headers=user_headers,
        json=_reset_payload(new_password=TEST_WEAK_PASSWORD, confirm_password=TEST_WEAK_PASSWORD),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_reset_password_mismatch_400(
    client: TestClient,
    user_headers: dict[str, str],
) -> None:
    response = client.post(
        RESET_PASSWORD_BASE,
        headers=user_headers,
        json=_reset_payload(confirm_password=TEST_DIFFERENT_PASSWORD),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_reset_password_same_as_current_409(
    client: TestClient,
    user_headers: dict[str, str],
) -> None:
    response = client.post(
        RESET_PASSWORD_BASE,
        headers=user_headers,
        json=_reset_payload(
            new_password=REGULAR_PASSWORD,
            confirm_password=REGULAR_PASSWORD,
        ),
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "PASSWORD_UNCHANGED"


def test_reset_password_empty_password_422(
    client: TestClient,
    user_headers: dict[str, str],
) -> None:
    response = client.post(
        RESET_PASSWORD_BASE,
        headers=user_headers,
        json={"new_password": "", "confirm_password": ""},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_validate_password_strength_valid_200(
    client: TestClient,
    user_headers: dict[str, str],
) -> None:
    response = client.get(
        VALIDATE_PASSWORD_BASE,
        headers=user_headers,
        params={"password": TEST_NEW_PASSWORD, "phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "valid"
    assert body["strength"] == "strong"
    assert body["requirements"]["min_length"] is True
    assert body["requirements"]["has_number"] is True
    assert body["requirements"]["has_special"] is True
    assert body["error"] is None
    assert body["password"] is None
    assert body["phone"] == "+1-555-0100"


def test_validate_password_strength_invalid_200(
    client: TestClient,
    user_headers: dict[str, str],
) -> None:
    response = client.get(
        VALIDATE_PASSWORD_BASE,
        headers=user_headers,
        params={"password": TEST_WEAK_PASSWORD_LONG},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "invalid"
    assert body["requirements"]["has_uppercase"] is False
    assert body["requirements"]["has_special"] is False


def test_validate_password_strength_empty_400(
    client: TestClient,
    user_headers: dict[str, str],
) -> None:
    response = client.get(VALIDATE_PASSWORD_BASE, headers=user_headers)
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_validate_password_strength_unauthorized_403(client: TestClient) -> None:
    response = client.get(VALIDATE_PASSWORD_BASE, params={"password": TEST_NEW_PASSWORD})
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "FORBIDDEN"

def test_reset_password_insufficient_strength_missing_special_400(
    client: TestClient,
    user_headers: dict[str, str],
) -> None:
    """HE-298: password missing special characters returns 400."""
    weak = "Password1234"
    response = client.post(
        RESET_PASSWORD_BASE,
        headers=user_headers,
        json=_reset_payload(new_password=weak, confirm_password=weak),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_reset_password_expired_jwt_403(
    client: TestClient,
    expired_user_headers: dict[str, str],
) -> None:
    """Auth: expired JWT cannot reset password."""
    response = client.post(
        RESET_PASSWORD_BASE,
        headers=expired_user_headers,
        json=_reset_payload(),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
