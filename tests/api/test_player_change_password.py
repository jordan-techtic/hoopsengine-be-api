"""Integration tests for authenticated player change password (HE-224)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from tests.conftest import (
    PLAYER_CHANGE_PASSWORD_BASE,
    TEST_DIFFERENT_PASSWORD,
    TEST_INVALID_PASSWORD,
    TEST_NEW_SECURE_PASSWORD,
    TEST_WEAK_PASSWORD,
    VIEWER_ID,
    VIEWER_PASSWORD,
    sync_engine,
)


def _change_password_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "current_password": VIEWER_PASSWORD,
        "new_password": TEST_NEW_SECURE_PASSWORD,
        "confirm_new_password": TEST_NEW_SECURE_PASSWORD,
        "phone": "+1-555-0100",
        "password": TEST_NEW_SECURE_PASSWORD,
    }
    payload.update(overrides)
    return payload


def _restore_viewer_password() -> None:
    with Session(sync_engine) as session:
        user = session.get(User, VIEWER_ID)
        assert user is not None
        user.encrypted_password = hash_password(VIEWER_PASSWORD)
        session.commit()


def test_change_password_success_200(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    try:
        response = client.post(
            PLAYER_CHANGE_PASSWORD_BASE,
            headers=viewer_headers,
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
        assert body["id"] == str(VIEWER_ID)
    finally:
        _restore_viewer_password()


def test_change_password_unauthenticated_401(client: TestClient) -> None:
    response = client.post(PLAYER_CHANGE_PASSWORD_BASE, json=_change_password_payload())
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


def test_change_password_empty_current_400(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.post(
        PLAYER_CHANGE_PASSWORD_BASE,
        headers=viewer_headers,
        json=_change_password_payload(current_password=""),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_change_password_wrong_current_400(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.post(
        PLAYER_CHANGE_PASSWORD_BASE,
        headers=viewer_headers,
        json=_change_password_payload(current_password=TEST_INVALID_PASSWORD),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "current_password"


def test_change_password_mismatch_409(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.post(
        PLAYER_CHANGE_PASSWORD_BASE,
        headers=viewer_headers,
        json=_change_password_payload(
            confirm_new_password=TEST_DIFFERENT_PASSWORD,
            password=TEST_DIFFERENT_PASSWORD,
        ),
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "PASSWORD_MISMATCH"
    assert body["error"]["details"][0]["field"] == "confirm_new_password"


def test_change_password_weak_400(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.post(
        PLAYER_CHANGE_PASSWORD_BASE,
        headers=viewer_headers,
        json=_change_password_payload(
            new_password=TEST_WEAK_PASSWORD,
            confirm_new_password=TEST_WEAK_PASSWORD,
            password=TEST_WEAK_PASSWORD,
        ),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_change_password_unchanged_409(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.post(
        PLAYER_CHANGE_PASSWORD_BASE,
        headers=viewer_headers,
        json=_change_password_payload(
            new_password=VIEWER_PASSWORD,
            confirm_new_password=VIEWER_PASSWORD,
            password=VIEWER_PASSWORD,
        ),
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "PASSWORD_UNCHANGED"
