"""Integration tests for authenticated player reset password (HE-220)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from tests.conftest import (
    PLAYER_RESET_PASSWORD_BASE,
    TEST_DIFFERENT_PASSWORD,
    TEST_NEW_SECURE_PASSWORD,
    TEST_WEAK_PASSWORD,
    VIEWER_ID,
    VIEWER_PASSWORD,
    sync_engine,
)


def _reset_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "new_password": TEST_NEW_SECURE_PASSWORD,
        "confirm_password": TEST_NEW_SECURE_PASSWORD,
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


def test_player_reset_password_success_201(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    try:
        response = client.post(
            PLAYER_RESET_PASSWORD_BASE,
            headers=viewer_headers,
            json=_reset_payload(),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["status"] == "password_reset"
        assert body["message"] == "Password has been reset successfully."
        assert body["description"]
        assert body["link"]
        assert "player/login" in body["link"]
        assert body["error"] is None
        assert body["password"] is None
        assert body["id"] == str(VIEWER_ID)
    finally:
        _restore_viewer_password()


def test_player_reset_password_unauthorized_401(client: TestClient) -> None:
    response = client.post(PLAYER_RESET_PASSWORD_BASE, json=_reset_payload())
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


def test_player_reset_password_forbidden_for_coach(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        PLAYER_RESET_PASSWORD_BASE,
        headers=coach_headers,
        json=_reset_payload(),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_player_reset_password_empty_new_password_400(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.post(
        PLAYER_RESET_PASSWORD_BASE,
        headers=viewer_headers,
        json=_reset_payload(new_password="   ", confirm_password="   "),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "new_password"


def test_player_reset_password_weak_password_400(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.post(
        PLAYER_RESET_PASSWORD_BASE,
        headers=viewer_headers,
        json=_reset_payload(
            new_password=TEST_WEAK_PASSWORD,
            confirm_password=TEST_WEAK_PASSWORD,
            password=TEST_WEAK_PASSWORD,
        ),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_player_reset_password_mismatch_400(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.post(
        PLAYER_RESET_PASSWORD_BASE,
        headers=viewer_headers,
        json=_reset_payload(confirm_password=TEST_DIFFERENT_PASSWORD),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "confirm_password"


def test_player_reset_password_same_as_current_409(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.post(
        PLAYER_RESET_PASSWORD_BASE,
        headers=viewer_headers,
        json=_reset_payload(
            new_password=VIEWER_PASSWORD,
            confirm_password=VIEWER_PASSWORD,
            password=VIEWER_PASSWORD,
        ),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PASSWORD_UNCHANGED"
