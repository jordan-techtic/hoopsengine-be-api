"""Integration tests for player login (HE-228)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from tests.conftest import (
    PLAYER_LOGIN_BASE,
    PLAYER_LOGIN_VALIDATE_BASE,
    REGULAR_EMAIL,
    REGULAR_PASSWORD,
    TEST_INVALID_PASSWORD,
    VIEWER_EMAIL,
    VIEWER_ID,
    VIEWER_PASSWORD,
    sync_engine,
)


def _login_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "email": VIEWER_EMAIL,
        "password": VIEWER_PASSWORD,
        "remember_me": False,
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


def _clear_player_session(user_id: object) -> None:
    with Session(sync_engine) as session:
        db_user = session.get(User, user_id)
        assert db_user is not None
        meta = dict(db_user.raw_user_meta_data or {})
        meta.pop("active_session_jti", None)
        meta.pop("active_session_exp", None)
        db_user.raw_user_meta_data = meta or None
        session.commit()


def test_player_login_valid_credentials_201_jwt(
    client: TestClient,
    seeded_users: dict,
) -> None:
    _clear_player_session(VIEWER_ID)
    response = client.post(PLAYER_LOGIN_BASE, json=_login_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["title"] == "LOGIN"
    assert body["message"] == "Login successful"
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in_hours"] == settings.ACCESS_TOKEN_EXPIRE_HOURS
    assert body["email"] == VIEWER_EMAIL
    assert body["username"] == "viewerplayer"
    assert body["id"] == str(VIEWER_ID)
    assert body["password"] is None
    assert body["error"] is None
    _clear_player_session(VIEWER_ID)


def test_player_login_by_username_201(
    client: TestClient,
    seeded_users: dict,
) -> None:
    _clear_player_session(VIEWER_ID)
    response = client.post(
        PLAYER_LOGIN_BASE,
        json=_login_payload(email="viewerplayer"),
    )
    assert response.status_code == 201
    assert response.json()["username"] == "viewerplayer"
    _clear_player_session(VIEWER_ID)


def test_player_login_empty_email_400(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        PLAYER_LOGIN_BASE,
        json=_login_payload(email="   "),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"


def test_player_login_empty_password_400(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        PLAYER_LOGIN_BASE,
        json=_login_payload(password="   "),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "password"


def test_player_login_invalid_email_format_400(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        PLAYER_LOGIN_BASE,
        json=_login_payload(email="not-an-email"),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"


def test_player_login_invalid_credentials_401(
    client: TestClient,
    seeded_users: dict,
) -> None:
    _clear_player_session(VIEWER_ID)
    response = client.post(
        PLAYER_LOGIN_BASE,
        json=_login_payload(password=TEST_INVALID_PASSWORD),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_player_login_coach_credentials_401(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        PLAYER_LOGIN_BASE,
        json={"email": REGULAR_EMAIL, "password": REGULAR_PASSWORD},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_player_login_remember_me_longer_expiry(
    client: TestClient,
    seeded_users: dict,
) -> None:
    _clear_player_session(VIEWER_ID)
    response = client.post(
        PLAYER_LOGIN_BASE,
        json=_login_payload(remember_me=True),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["remember_me"] is True
    assert body["expires_in_hours"] == settings.REMEMBER_ME_TOKEN_EXPIRE_HOURS
    _clear_player_session(VIEWER_ID)


def test_player_login_duplicate_session_409(
    client: TestClient,
    seeded_users: dict,
) -> None:
    _clear_player_session(VIEWER_ID)
    first = client.post(PLAYER_LOGIN_BASE, json=_login_payload())
    assert first.status_code == 201

    second = client.post(PLAYER_LOGIN_BASE, json=_login_payload())
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DUPLICATE_SESSION"
    _clear_player_session(VIEWER_ID)


def test_player_login_validate_valid_200(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.get(
        PLAYER_LOGIN_VALIDATE_BASE,
        params={"email": VIEWER_EMAIL, "password": VIEWER_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["title"] == "LOGIN"
    assert body["status"] == "valid"
    assert body["errors"] is None


def test_player_login_validate_missing_fields_200_invalid(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.get(
        PLAYER_LOGIN_VALIDATE_BASE,
        params={"email": "", "password": ""},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["status"] == "invalid"
    assert body["errors"]
    fields = {item["field"] for item in body["errors"]}
    assert "email" in fields
    assert "password" in fields


def test_player_login_validate_invalid_email_200_invalid(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.get(
        PLAYER_LOGIN_VALIDATE_BASE,
        params={"email": "bad-email", "password": VIEWER_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert any(error["field"] == "email" for error in body["errors"])
