"""Integration tests for coach cancel/continue verification endpoints (HE-297)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_otp
from app.models.user import User
from tests.conftest import (
    COACH_CANCEL_VERIFICATION_BASE,
    COACH_CONTINUE_VERIFICATION_BASE,
    TEST_OTP_CODE,
    UNVERIFIED_COACH_EMAIL,
    UNVERIFIED_COACH_ID,
    sync_engine,
)

CANCEL_BASE = COACH_CANCEL_VERIFICATION_BASE
CONTINUE_BASE = COACH_CONTINUE_VERIFICATION_BASE


def _cancel_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "cancel_verification": True,
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


def _reset_unverified_otp(user: User) -> None:
    with Session(sync_engine) as session:
        db_user = session.get(User, user.id)
        assert db_user is not None
        db_user.email_confirmed_at = None
        db_user.confirmation_token = hash_otp(TEST_OTP_CODE)
        db_user.confirmation_sent_at = datetime.now(timezone.utc)
        db_user.deleted_at = None
        db_user.is_active = True
        session.commit()


def _mark_verified(user: User) -> None:
    with Session(sync_engine) as session:
        db_user = session.get(User, user.id)
        assert db_user is not None
        db_user.email_confirmed_at = datetime.now(timezone.utc)
        session.commit()


def _clear_verification_state(user: User) -> None:
    with Session(sync_engine) as session:
        db_user = session.get(User, user.id)
        assert db_user is not None
        db_user.email_confirmed_at = None
        db_user.confirmation_token = None
        db_user.confirmation_sent_at = None
        db_user.deleted_at = None
        db_user.is_active = True
        session.commit()


def test_cancel_verification_success_201(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
    unverified_coach_user: User,
) -> None:
    _reset_unverified_otp(unverified_coach_user)
    response = client.post(
        CANCEL_BASE,
        headers=unverified_coach_headers,
        json=_cancel_payload(),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "cancelled"
    assert body["message"]
    assert body["description"]
    assert body["link"]
    assert body["error"] is None
    assert body["id"] == str(UNVERIFIED_COACH_ID)


def test_cancel_verification_unauthorized_403(client: TestClient) -> None:
    response = client.post(CANCEL_BASE, json=_cancel_payload())
    assert response.status_code == 403
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "FORBIDDEN"


def test_cancel_verification_empty_body_400(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
    unverified_coach_user: User,
) -> None:
    _reset_unverified_otp(unverified_coach_user)
    response = client.post(CANCEL_BASE, headers=unverified_coach_headers, json={})
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_cancel_verification_missing_flag_400(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
    unverified_coach_user: User,
) -> None:
    _reset_unverified_otp(unverified_coach_user)
    response = client.post(
        CANCEL_BASE,
        headers=unverified_coach_headers,
        json={"cancel_verification": False, "phone": "+1-555-0100"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_cancel_verification_already_verified_409(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
    unverified_coach_user: User,
) -> None:
    _mark_verified(unverified_coach_user)
    response = client.post(
        CANCEL_BASE,
        headers=unverified_coach_headers,
        json=_cancel_payload(),
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "VERIFICATION_ALREADY_COMPLETED"


def test_cancel_verification_not_in_progress_409(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
    unverified_coach_user: User,
) -> None:
    _clear_verification_state(unverified_coach_user)
    response = client.post(
        CANCEL_BASE,
        headers=unverified_coach_headers,
        json=_cancel_payload(),
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "VERIFICATION_NOT_IN_PROGRESS"


def test_continue_verification_success_200(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
    unverified_coach_user: User,
) -> None:
    _reset_unverified_otp(unverified_coach_user)
    response = client.get(
        CONTINUE_BASE,
        headers=unverified_coach_headers,
        params={"phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "pending_verification"
    assert body["message"]
    assert body["description"]
    assert body["link"]
    assert body["error"] is None
    assert body["email"] == UNVERIFIED_COACH_EMAIL
    assert body["phone"] == "+1-555-0100"
    assert body["id"] == str(UNVERIFIED_COACH_ID)


def test_continue_verification_unauthorized_403(client: TestClient) -> None:
    response = client.get(CONTINUE_BASE)
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "FORBIDDEN"


def test_continue_verification_already_verified_409(
    client: TestClient,
    unverified_coach_headers: dict[str, str],
    unverified_coach_user: User,
) -> None:
    _mark_verified(unverified_coach_user)
    response = client.get(CONTINUE_BASE, headers=unverified_coach_headers)
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "VERIFICATION_ALREADY_COMPLETED"
