"""Unit tests for player password recovery service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.security import hash_otp
from app.models.user import User
from app.services import player_recovery as player_recovery_service


def test_normalize_email_empty_raises_400() -> None:
    with pytest.raises(AppException) as exc_info:
        player_recovery_service._normalize_email("   ")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_normalize_email_invalid_raises_400() -> None:
    with pytest.raises(AppException) as exc_info:
        player_recovery_service._normalize_email("not-an-email")
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "email"


def test_validate_verification_code_invalid_format() -> None:
    with pytest.raises(AppException) as exc_info:
        player_recovery_service._validate_verification_code("abc")
    assert exc_info.value.code == "INVALID_VERIFICATION_CODE"


def test_recovery_otp_is_expired() -> None:
    user = User(
        email="player@test.com",
        encrypted_password="hash",
        role="player",
        recovery_sent_at=datetime.now(timezone.utc)
        - timedelta(minutes=settings.PASSWORD_RECOVERY_OTP_EXPIRE_MINUTES + 5),
    )
    assert player_recovery_service._recovery_otp_is_expired(user) is True


@pytest.mark.asyncio
async def test_request_recovery_non_player_raises_404() -> None:
    db = AsyncMock()
    with patch(
        "app.services.player_recovery.auth_service.get_user_by_email",
        new=AsyncMock(
            return_value=User(
                email="coach@test.com",
                encrypted_password="hash",
                role="coach",
                is_active=True,
            )
        ),
    ):
        with pytest.raises(AppException) as exc_info:
            await player_recovery_service.request_player_password_recovery(db, "coach@test.com")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_verify_recovery_otp_matches() -> None:
    db = AsyncMock()
    user = User(
        id=uuid4(),
        email="player@test.com",
        encrypted_password="hash",
        role="player",
        is_active=True,
        recovery_token=hash_otp("123456"),
        recovery_sent_at=datetime.now(timezone.utc),
    )
    with patch(
        "app.services.player_recovery._get_player_by_email",
        new=AsyncMock(return_value=user),
    ):
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        verified_user, reset_token = await player_recovery_service.verify_player_recovery_code(
            db,
            email="player@test.com",
            verification_code="123456",
        )

    assert verified_user.email == "player@test.com"
    assert reset_token is not None
    db.commit.assert_awaited_once()
