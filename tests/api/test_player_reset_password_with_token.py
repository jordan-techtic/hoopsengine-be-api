"""Integration tests for player reset-password-with-token flow (HE-227)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_otp, hash_password, verify_password
from app.models.user import User
from tests.conftest import (
    PLAYER_FORGOT_PASSWORD_BASE,
    PLAYER_LOGIN_BASE,
    PLAYER_RESET_PASSWORD_WITH_TOKEN_BASE,
    PLAYER_VERIFY_CODE_BASE,
    TEST_DIFFERENT_PASSWORD,
    TEST_NEW_SECURE_PASSWORD,
    TEST_OTP_CODE,
    TEST_WEAK_PASSWORD,
    VIEWER_EMAIL,
    VIEWER_ID,
    VIEWER_PASSWORD,
    sync_engine,
)


def _forgot_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"email": VIEWER_EMAIL, "phone": "+1-555-0100"}
    payload.update(overrides)
    return payload


def _verify_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "email": VIEWER_EMAIL,
        "verification_code": TEST_OTP_CODE,
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


def _reset_with_token_payload(reset_token: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "reset_token": reset_token,
        "new_password": TEST_NEW_SECURE_PASSWORD,
        "confirm_password": TEST_NEW_SECURE_PASSWORD,
        "phone": "+1-555-0100",
        "password": TEST_NEW_SECURE_PASSWORD,
    }
    payload.update(overrides)
    return payload


def _seed_recovery_otp(user_id: object, *, sent_at: datetime | None = None) -> None:
    with Session(sync_engine) as session:
        db_user = session.get(User, user_id)
        assert db_user is not None
        db_user.recovery_token = hash_otp(TEST_OTP_CODE)
        db_user.recovery_sent_at = sent_at or datetime.now(timezone.utc)
        session.commit()


def _clear_recovery_state(user_id: object) -> None:
    with Session(sync_engine) as session:
        db_user = session.get(User, user_id)
        assert db_user is not None
        db_user.recovery_token = None
        db_user.recovery_sent_at = None
        session.commit()


def _restore_viewer_password() -> None:
    with Session(sync_engine) as session:
        user = session.get(User, VIEWER_ID)
        assert user is not None
        user.encrypted_password = hash_password(VIEWER_PASSWORD)
        user.recovery_token = None
        user.recovery_sent_at = None
        session.commit()


def _obtain_reset_token(client: TestClient) -> str:
    _clear_recovery_state(VIEWER_ID)
    _seed_recovery_otp(VIEWER_ID)
    response = client.post(PLAYER_VERIFY_CODE_BASE, json=_verify_payload())
    assert response.status_code == 200
    reset_token = response.json().get("reset_token")
    assert reset_token
    return reset_token


def test_reset_password_with_token_success_201(
    client: TestClient,
    seeded_users: dict,
) -> None:
    """HE-227: User resets password via recovery token after OTP verify-only step."""
    try:
        reset_token = _obtain_reset_token(client)
        response = client.post(
            PLAYER_RESET_PASSWORD_WITH_TOKEN_BASE,
            json=_reset_with_token_payload(reset_token),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["status"] == "password_reset"
        assert body["message"] == "Password has been reset successfully."
        assert "player/login" in body["link"]
        assert body["id"] == str(VIEWER_ID)
        assert body["error"] is None

        with Session(sync_engine) as session:
            db_user = session.get(User, VIEWER_ID)
            assert db_user is not None
            assert verify_password(TEST_NEW_SECURE_PASSWORD, db_user.encrypted_password)
            assert db_user.recovery_token is None
    finally:
        _restore_viewer_password()


def test_reset_password_with_token_full_flow_login_201(
    client: TestClient,
    seeded_users: dict,
) -> None:
    """HE-227: forgot-password → verify-code → reset-with-token → login with new password."""
    try:
        _clear_recovery_state(VIEWER_ID)
        with patch("app.services.player_recovery.send_password_recovery_email"):
            with patch(
                "app.services.player_recovery.generate_otp_code",
                return_value=TEST_OTP_CODE,
            ):
                forgot = client.post(PLAYER_FORGOT_PASSWORD_BASE, json=_forgot_payload())
        assert forgot.status_code == 201

        verify = client.post(
            PLAYER_VERIFY_CODE_BASE,
            json=_verify_payload(verification_code=TEST_OTP_CODE),
        )
        assert verify.status_code == 200
        reset_token = verify.json()["reset_token"]
        assert reset_token

        reset = client.post(
            PLAYER_RESET_PASSWORD_WITH_TOKEN_BASE,
            json=_reset_with_token_payload(reset_token),
        )
        assert reset.status_code == 201

        login = client.post(
            PLAYER_LOGIN_BASE,
            json={
                "email": VIEWER_EMAIL,
                "password": TEST_NEW_SECURE_PASSWORD,
                "remember_me": False,
                "phone": "+1-555-0100",
            },
        )
        assert login.status_code == 201
        assert login.json()["access_token"]
    finally:
        _restore_viewer_password()


def test_reset_password_with_token_invalid_token_400(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        PLAYER_RESET_PASSWORD_WITH_TOKEN_BASE,
        json=_reset_with_token_payload("not-a-valid-reset-token"),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_RESET_TOKEN"


def test_reset_password_with_token_empty_token_400(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        PLAYER_RESET_PASSWORD_WITH_TOKEN_BASE,
        json=_reset_with_token_payload("   "),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "reset_token"


def test_reset_password_with_token_expired_403(
    client: TestClient,
    seeded_users: dict,
) -> None:
    """HE-227: expired reset token returns 403 RESET_TOKEN_EXPIRED."""
    reset_token = _obtain_reset_token(client)
    expired_sent_at = datetime.now(timezone.utc) - timedelta(
        hours=settings.RESET_TOKEN_EXPIRE_HOURS + 1
    )
    with Session(sync_engine) as session:
        db_user = session.get(User, VIEWER_ID)
        assert db_user is not None
        db_user.recovery_sent_at = expired_sent_at
        session.commit()

    response = client.post(
        PLAYER_RESET_PASSWORD_WITH_TOKEN_BASE,
        json=_reset_with_token_payload(reset_token),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "RESET_TOKEN_EXPIRED"
    _restore_viewer_password()


def test_reset_password_with_token_weak_password_400(
    client: TestClient,
    seeded_users: dict,
) -> None:
    reset_token = _obtain_reset_token(client)
    response = client.post(
        PLAYER_RESET_PASSWORD_WITH_TOKEN_BASE,
        json=_reset_with_token_payload(
            reset_token,
            new_password=TEST_WEAK_PASSWORD,
            confirm_password=TEST_WEAK_PASSWORD,
            password=TEST_WEAK_PASSWORD,
        ),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    _restore_viewer_password()


def test_reset_password_with_token_password_mismatch_400(
    client: TestClient,
    seeded_users: dict,
) -> None:
    reset_token = _obtain_reset_token(client)
    response = client.post(
        PLAYER_RESET_PASSWORD_WITH_TOKEN_BASE,
        json=_reset_with_token_payload(
            reset_token,
            confirm_password=TEST_DIFFERENT_PASSWORD,
        ),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    _restore_viewer_password()


def test_reset_password_with_token_no_auth_required_201(
    client: TestClient,
    seeded_users: dict,
) -> None:
    """Public endpoint: no Authorization header needed."""
    try:
        reset_token = _obtain_reset_token(client)
        response = client.post(
            PLAYER_RESET_PASSWORD_WITH_TOKEN_BASE,
            json=_reset_with_token_payload(reset_token),
        )
        assert response.status_code == 201
    finally:
        _restore_viewer_password()


def test_verify_recovery_code_returns_reset_token_200(
    client: TestClient,
    seeded_users: dict,
) -> None:
    """HE-227: verify-only response includes reset_token for FE Reset Password screen."""
    _clear_recovery_state(VIEWER_ID)
    _seed_recovery_otp(VIEWER_ID)
    response = client.post(PLAYER_VERIFY_CODE_BASE, json=_verify_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["reset_token"]
    assert len(body["reset_token"]) > 10
    assert body["link"] == settings.PLAYER_RESET_PASSWORD_URL
    _restore_viewer_password()
