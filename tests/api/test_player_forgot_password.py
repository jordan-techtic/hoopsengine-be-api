"""Integration tests for player forgot-password and verify-code (HE-227)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_otp, verify_password
from app.models.user import User
from tests.conftest import (
    PLAYER_FORGOT_PASSWORD_BASE,
    PLAYER_VERIFY_CODE_BASE,
    TEST_NEW_SECURE_PASSWORD,
    TEST_OTP_CODE,
    TEST_WEAK_PASSWORD,
    VIEWER_EMAIL,
    VIEWER_ID,
    VIEWER_PASSWORD,
    sync_engine,
)


def _forgot_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "email": VIEWER_EMAIL,
        "phone": "+1-555-0100",
    }
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


def _seed_recovery_otp(
    user_id: object,
    *,
    otp_code: str = TEST_OTP_CODE,
    sent_at: datetime | None = None,
) -> None:
    with Session(sync_engine) as session:
        db_user = session.get(User, user_id)
        assert db_user is not None
        db_user.recovery_token = hash_otp(otp_code)
        db_user.recovery_sent_at = sent_at or datetime.now(timezone.utc)
        session.commit()


def _clear_recovery_otp(user_id: object) -> None:
    with Session(sync_engine) as session:
        db_user = session.get(User, user_id)
        assert db_user is not None
        db_user.recovery_token = None
        db_user.recovery_sent_at = None
        session.commit()


def test_forgot_password_registered_email_201(
    client: TestClient,
    seeded_users: dict,
) -> None:
    _clear_recovery_otp(VIEWER_ID)
    with patch("app.services.player_recovery.send_password_recovery_email") as send_email:
        response = client.post(PLAYER_FORGOT_PASSWORD_BASE, json=_forgot_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert "verification code" in body["message"].lower()
    assert body["status"] == "recovery_code_sent"
    assert body["email"] == VIEWER_EMAIL
    assert body["link"] == settings.PLAYER_RESET_PASSWORD_URL
    assert body["error"] is None
    send_email.assert_called_once()


def test_forgot_password_sends_recovery_email(
    client: TestClient,
    seeded_users: dict,
) -> None:
    _clear_recovery_otp(VIEWER_ID)
    with patch("app.services.player_recovery.send_password_recovery_email") as send_email:
        client.post(PLAYER_FORGOT_PASSWORD_BASE, json=_forgot_payload())
    send_email.assert_called_once_with(VIEWER_EMAIL, send_email.call_args[0][1])


def test_forgot_password_unregistered_email_404(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        PLAYER_FORGOT_PASSWORD_BASE,
        json=_forgot_payload(email="unknown.player@example.com"),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


def test_forgot_password_invalid_email_format_400(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        PLAYER_FORGOT_PASSWORD_BASE,
        json=_forgot_payload(email="not-an-email"),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"


def test_forgot_password_empty_email_400(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        PLAYER_FORGOT_PASSWORD_BASE,
        json=_forgot_payload(email="   "),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"


def test_forgot_password_coach_email_404(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        PLAYER_FORGOT_PASSWORD_BASE,
        json=_forgot_payload(email=seeded_users["user"]["email"]),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


def test_verify_recovery_code_valid_200(
    client: TestClient,
    seeded_users: dict,
) -> None:
    _seed_recovery_otp(VIEWER_ID)
    response = client.post(PLAYER_VERIFY_CODE_BASE, json=_verify_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "verified"
    assert body["email"] == VIEWER_EMAIL
    assert body["id"] == str(VIEWER_ID)
    assert body["verification_code"] is None
    assert body["password"] is None
    assert body["error"] is None


def test_verify_recovery_code_invalid_400(
    client: TestClient,
    seeded_users: dict,
) -> None:
    _seed_recovery_otp(VIEWER_ID)
    response = client.post(
        PLAYER_VERIFY_CODE_BASE,
        json=_verify_payload(verification_code="000000"),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_VERIFICATION_CODE"


def test_verify_recovery_code_expired_403(
    client: TestClient,
    seeded_users: dict,
) -> None:
    _seed_recovery_otp(
        VIEWER_ID,
        sent_at=datetime.now(timezone.utc)
        - timedelta(minutes=settings.PASSWORD_RECOVERY_OTP_EXPIRE_MINUTES + 1),
    )
    response = client.post(PLAYER_VERIFY_CODE_BASE, json=_verify_payload())
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "RECOVERY_CODE_EXPIRED"


def test_verify_recovery_code_empty_code_400(
    client: TestClient,
    seeded_users: dict,
) -> None:
    _seed_recovery_otp(VIEWER_ID)
    response = client.post(
        PLAYER_VERIFY_CODE_BASE,
        json=_verify_payload(verification_code="   "),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_verify_recovery_code_unregistered_email_404(
    client: TestClient,
    seeded_users: dict,
) -> None:
    response = client.post(
        PLAYER_VERIFY_CODE_BASE,
        json=_verify_payload(email="missing.player@example.com"),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


def test_verify_recovery_code_resets_password_200(
    client: TestClient,
    seeded_users: dict,
) -> None:
    _seed_recovery_otp(VIEWER_ID)
    response = client.post(
        PLAYER_VERIFY_CODE_BASE,
        json=_verify_payload(
            password=TEST_NEW_SECURE_PASSWORD,
            confirm_password=TEST_NEW_SECURE_PASSWORD,
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "password_reset"
    assert "reset" in body["message"].lower()

    with Session(sync_engine) as session:
        db_user = session.get(User, VIEWER_ID)
        assert db_user is not None
        assert verify_password(TEST_NEW_SECURE_PASSWORD, db_user.encrypted_password)
        assert db_user.recovery_token is None
        from app.core.security import hash_password

        db_user.encrypted_password = hash_password(VIEWER_PASSWORD)
        session.commit()


def test_verify_recovery_code_weak_password_400(
    client: TestClient,
    seeded_users: dict,
) -> None:
    _seed_recovery_otp(VIEWER_ID)
    response = client.post(
        PLAYER_VERIFY_CODE_BASE,
        json=_verify_payload(
            password=TEST_WEAK_PASSWORD,
            confirm_password=TEST_WEAK_PASSWORD,
        ),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_verify_recovery_code_password_mismatch_400(
    client: TestClient,
    seeded_users: dict,
) -> None:
    _seed_recovery_otp(VIEWER_ID)
    response = client.post(
        PLAYER_VERIFY_CODE_BASE,
        json=_verify_payload(
            password=TEST_NEW_SECURE_PASSWORD,
            confirm_password=VIEWER_PASSWORD,
        ),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "confirm_password"


def test_forgot_password_resend_cooldown_429(
    client: TestClient,
    seeded_users: dict,
) -> None:
    _seed_recovery_otp(VIEWER_ID, sent_at=datetime.now(timezone.utc))
    response = client.post(PLAYER_FORGOT_PASSWORD_BASE, json=_forgot_payload())
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RESEND_COOLDOWN"
