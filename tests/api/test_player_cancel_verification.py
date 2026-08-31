"""Integration tests for player cancel verification endpoints (HE-218)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_otp
from app.models.user import User
from tests.conftest import (
    PLAYER_CANCEL_VERIFICATION_BASE,
    TEST_OTP_CODE,
    UNVERIFIED_PLAYER_ID,
    sync_engine,
)


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


def test_post_cancel_verification_success_201(
    client: TestClient,
    unverified_player_headers: dict[str, str],
    unverified_player_user: User,
) -> None:
    _reset_unverified_otp(unverified_player_user)
    response = client.post(
        PLAYER_CANCEL_VERIFICATION_BASE,
        headers=unverified_player_headers,
        json=_cancel_payload(),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "cancelled"
    assert "cancelled" in body["message"].lower()
    assert body["description"]
    assert body["link"]
    assert body["error"] is None
    assert body["id"] == str(UNVERIFIED_PLAYER_ID)


def test_post_cancel_verification_missing_fields_400(
    client: TestClient,
    unverified_player_headers: dict[str, str],
    unverified_player_user: User,
) -> None:
    _reset_unverified_otp(unverified_player_user)
    response = client.post(
        PLAYER_CANCEL_VERIFICATION_BASE,
        headers=unverified_player_headers,
        json={},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_post_cancel_verification_unauthenticated_409(client: TestClient) -> None:
    response = client.post(PLAYER_CANCEL_VERIFICATION_BASE, json=_cancel_payload())
    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHENTICATED"


def test_get_cancel_verification_instructions_200(
    client: TestClient,
    unverified_player_headers: dict[str, str],
    unverified_player_user: User,
) -> None:
    _reset_unverified_otp(unverified_player_user)
    response = client.get(
        PLAYER_CANCEL_VERIFICATION_BASE,
        headers=unverified_player_headers,
        params={"phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "ready"
    assert body["heading"] == "Cancel Verification?"
    assert "Cancelling will stop the verification process" in body["instructions"]
    assert body["message"]
    assert body["description"]
    assert body["link"]
    assert body["error"] is None
    assert body["phone"] == "+1-555-0100"
    assert body["id"] == str(UNVERIFIED_PLAYER_ID)


def test_post_cancel_verification_includes_processed_message(
    client: TestClient,
    unverified_player_headers: dict[str, str],
    unverified_player_user: User,
) -> None:
    _reset_unverified_otp(unverified_player_user)
    response = client.post(
        PLAYER_CANCEL_VERIFICATION_BASE,
        headers=unverified_player_headers,
        json=_cancel_payload(),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "Verification cancelled successfully."
