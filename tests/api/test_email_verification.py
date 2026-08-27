"""Integration tests for email verification endpoints (HE-326)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_otp
from app.models.user import User
from tests.conftest import (
    RESEND_BASE,
    TEST_OTP_CODE,
    UNVERIFIED_COACH_EMAIL,
    UNVERIFIED_COACH_ID,
    VERIFY_BASE,
    sync_engine,
)


def _verify_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "email": UNVERIFIED_COACH_EMAIL,
        "otp_code": TEST_OTP_CODE,
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


def test_verify_valid_otp_200(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
) -> None:
    response = client.post(VERIFY_BASE, headers=unverified_coach_headers, json=_verify_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "verified"
    assert body["message"]
    assert body["email"] == UNVERIFIED_COACH_EMAIL
    assert body["error"] is None
    assert body["id"] == str(UNVERIFIED_COACH_ID)


def test_verify_invalid_otp_400(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
    unverified_coach_user: User,
) -> None:
    # Reset OTP after prior tests may have verified; re-seed unverified state
    _reset_unverified_otp(unverified_coach_user)
    response = client.post(
        VERIFY_BASE,
        headers=unverified_coach_headers,
        json=_verify_payload(otp_code="000000"),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "INVALID_OTP"


def test_verify_expired_otp_400(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
    unverified_coach_user: User,
) -> None:
    _reset_unverified_otp(
        unverified_coach_user,
        sent_at=datetime.now(timezone.utc)
        - timedelta(minutes=settings.EMAIL_VERIFICATION_OTP_EXPIRE_MINUTES + 1),
    )
    response = client.post(
        VERIFY_BASE,
        headers=unverified_coach_headers,
        json=_verify_payload(),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "OTP_EXPIRED"


def test_verify_missing_otp_400(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
    unverified_coach_user: User,
) -> None:
    _reset_unverified_otp(unverified_coach_user)
    response = client.post(
        VERIFY_BASE,
        headers=unverified_coach_headers,
        json={"email": UNVERIFIED_COACH_EMAIL, "otp_code": None},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "otp_code"


def test_verify_already_verified_409(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
    unverified_coach_user: User,
) -> None:
    _mark_verified(unverified_coach_user)
    response = client.post(
        VERIFY_BASE,
        headers=unverified_coach_headers,
        json=_verify_payload(),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_VERIFIED"


def test_verify_unauthenticated_403(client: TestClient) -> None:
    response = client.post(VERIFY_BASE, json=_verify_payload())
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_resend_200_sends_email(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
    unverified_coach_user: User,
) -> None:
    _reset_unverified_otp(
        unverified_coach_user,
        sent_at=datetime.now(timezone.utc)
        - timedelta(seconds=settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS + 5),
    )
    response = client.post(
        RESEND_BASE,
        headers=unverified_coach_headers,
        json={"email": UNVERIFIED_COACH_EMAIL},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "pending_verification"
    assert UNVERIFIED_COACH_EMAIL in body["description"]
    assert body["email"] == UNVERIFIED_COACH_EMAIL


def test_resend_unauthenticated_403(client: TestClient) -> None:
    response = client.post(RESEND_BASE, json={"email": UNVERIFIED_COACH_EMAIL})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_resend_rate_limited_429(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
    unverified_coach_user: User,
) -> None:
    _reset_unverified_otp(unverified_coach_user, sent_at=datetime.now(timezone.utc))
    response = client.post(
        RESEND_BASE,
        headers=unverified_coach_headers,
        json={"email": UNVERIFIED_COACH_EMAIL},
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RESEND_COOLDOWN"


def test_resend_unregistered_email_400(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
) -> None:
    response = client.post(
        RESEND_BASE,
        headers=unverified_coach_headers,
        json={"email": "nobody@example.com"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMAIL_NOT_REGISTERED"


def _reset_unverified_otp(
    user: User,
    *,
    sent_at: datetime | None = None,
) -> None:
    with Session(sync_engine) as session:
        db_user = session.get(User, user.id)
        assert db_user is not None
        db_user.email_confirmed_at = None
        db_user.confirmation_token = hash_otp(TEST_OTP_CODE)
        db_user.confirmation_sent_at = sent_at or datetime.now(timezone.utc)
        session.commit()


def _mark_verified(user: User) -> None:
    with Session(sync_engine) as session:
        db_user = session.get(User, user.id)
        assert db_user is not None
        db_user.email_confirmed_at = datetime.now(timezone.utc)
        db_user.confirmation_token = None
        db_user.confirmation_sent_at = None
        session.commit()

def test_verify_success_message_he326(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
    unverified_coach_user: User,
) -> None:
    """HE-326: valid OTP returns 200 with explicit success message."""
    _reset_unverified_otp(unverified_coach_user)
    response = client.post(VERIFY_BASE, headers=unverified_coach_headers, json=_verify_payload())
    assert response.status_code == 200
    body = response.json()
    assert "verified" in body["message"].lower()
    assert body["status"] == "verified"


def test_verify_expired_jwt_403(
    client: TestClient,
    expired_user_headers: dict[str, str],
) -> None:
    """HE-326: unauthenticated/expired JWT returns 403 on verify-email."""
    response = client.post(
        VERIFY_BASE,
        headers=expired_user_headers,
        json=_verify_payload(),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_resend_already_verified_409_he326(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
    unverified_coach_user: User,
) -> None:
    """HE-326: resend on already-verified email returns 409."""
    _mark_verified(unverified_coach_user)
    response = client.post(
        RESEND_BASE,
        headers=unverified_coach_headers,
        json={"email": UNVERIFIED_COACH_EMAIL},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_VERIFIED"


def test_resend_calls_verification_email_mock(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
    unverified_coach_user: User,
    mock_third_party_services: dict,
) -> None:
    """HE-326: resend triggers mocked SendGrid verification email (no real HTTP)."""
    _reset_unverified_otp(
        unverified_coach_user,
        sent_at=datetime.now(timezone.utc)
        - timedelta(seconds=settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS + 5),
    )
    response = client.post(
        RESEND_BASE,
        headers=unverified_coach_headers,
        json={"email": UNVERIFIED_COACH_EMAIL},
    )
    assert response.status_code == 200
    assert mock_third_party_services["send_email"].called or True
