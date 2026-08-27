"""Unit tests for email verification service."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.security import hash_otp
from app.models.enums import UserRole
from app.models.user import User
from app.services.email_verification import resend_verification_code, verify_email_otp


def _unverified_user(**overrides: object) -> User:
    now = datetime.now(timezone.utc)
    values: dict[str, object] = {
        "id": uuid4(),
        "email": "coach@example.com",
        "username": "coachuser",
        "encrypted_password": "hashed",
        "role": UserRole.COACH.value,
        "is_super_admin": False,
        "is_active": True,
        "email_confirmed_at": None,
        "confirmation_token": hash_otp("123456"),
        "confirmation_sent_at": now,
        "created_at": now,
    }
    values.update(overrides)
    return User(**values)


@patch("app.services.email_verification.send_verification_email")
def test_verify_email_otp_success(_mock_send: object) -> None:
    user = _unverified_user()
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda obj: obj)

    async def _run() -> User:
        return await verify_email_otp(db, current_user=user, otp_code="123456")

    result = asyncio.run(_run())
    assert result.email_confirmed_at is not None
    assert result.confirmation_token is None
    db.commit.assert_awaited_once()


def test_verify_invalid_otp_raises_400() -> None:
    user = _unverified_user()

    async def _run() -> None:
        await verify_email_otp(AsyncMock(), current_user=user, otp_code="654321")

    with pytest.raises(AppException) as exc_info:
        asyncio.run(_run())
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_OTP"


def test_verify_expired_otp_raises_400() -> None:
    expired_at = datetime.now(timezone.utc) - timedelta(
        minutes=settings.EMAIL_VERIFICATION_OTP_EXPIRE_MINUTES + 1
    )
    user = _unverified_user(confirmation_sent_at=expired_at)

    async def _run() -> None:
        await verify_email_otp(AsyncMock(), current_user=user, otp_code="123456")

    with pytest.raises(AppException) as exc_info:
        asyncio.run(_run())
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "OTP_EXPIRED"


def test_verify_missing_otp_raises_400() -> None:
    user = _unverified_user()

    async def _run() -> None:
        await verify_email_otp(AsyncMock(), current_user=user, otp_code=None)

    with pytest.raises(AppException) as exc_info:
        asyncio.run(_run())
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "otp_code"


def test_verify_already_verified_raises_409() -> None:
    user = _unverified_user(email_confirmed_at=datetime.now(timezone.utc))

    async def _run() -> None:
        await verify_email_otp(AsyncMock(), current_user=user, otp_code="123456")

    with pytest.raises(AppException) as exc_info:
        asyncio.run(_run())
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "EMAIL_ALREADY_VERIFIED"


@patch("app.services.email_verification.send_verification_email")
def test_resend_generates_new_otp(_mock_send: object) -> None:
    old_sent = datetime.now(timezone.utc) - timedelta(
        seconds=settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS + 5
    )
    user = _unverified_user(confirmation_sent_at=old_sent)
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda obj: obj)

    async def _run() -> User:
        return await resend_verification_code(db, current_user=user)

    result = asyncio.run(_run())
    assert result.confirmation_token is not None
    assert result.confirmation_token != hash_otp("123456")
    _mock_send.assert_called_once()


@patch("app.services.email_verification.send_verification_email")
def test_resend_rate_limit_raises_429(_mock_send: object) -> None:
    user = _unverified_user(confirmation_sent_at=datetime.now(timezone.utc))

    async def _run() -> None:
        await resend_verification_code(AsyncMock(), current_user=user)

    with pytest.raises(AppException) as exc_info:
        asyncio.run(_run())
    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "RESEND_COOLDOWN"
    _mock_send.assert_not_called()
