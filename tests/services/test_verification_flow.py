"""Unit tests for verification flow service (HE-297)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import AppException
from app.models.enums import UserRole
from app.models.user import User
from app.services import verification_flow as verification_flow_service


def _unverified_user(*, with_otp: bool = True) -> User:
    return User(
        id=MagicMock(),
        email="coach@test.com",
        encrypted_password="hashed",
        role=UserRole.COACH.value,
        is_active=True,
        email_confirmed_at=None,
        confirmation_token="otp-hash" if with_otp else None,
        confirmation_sent_at=datetime.now(timezone.utc) if with_otp else None,
    )


@pytest.mark.asyncio
async def test_cancel_verification_soft_deletes_user() -> None:
    user = _unverified_user()
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda u: u)

    result = await verification_flow_service.cancel_verification(db, user=user)

    assert result.is_active is False
    assert result.deleted_at is not None
    assert result.confirmation_token is None
    assert result.confirmation_sent_at is None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_verification_rejects_already_verified() -> None:
    user = _unverified_user()
    user.email_confirmed_at = datetime.now(timezone.utc)
    db = AsyncMock()

    with pytest.raises(AppException) as exc_info:
        await verification_flow_service.cancel_verification(db, user=user)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "VERIFICATION_ALREADY_COMPLETED"


@pytest.mark.asyncio
async def test_cancel_verification_rejects_not_in_progress() -> None:
    user = _unverified_user(with_otp=False)
    db = AsyncMock()

    with pytest.raises(AppException) as exc_info:
        await verification_flow_service.cancel_verification(db, user=user)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "VERIFICATION_NOT_IN_PROGRESS"


@pytest.mark.asyncio
async def test_continue_verification_returns_pending_user() -> None:
    user = _unverified_user()
    db = AsyncMock()

    result = await verification_flow_service.continue_verification(db, user=user)

    assert result.email == "coach@test.com"
    assert result.confirmation_token == "otp-hash"


@pytest.mark.asyncio
async def test_continue_verification_rejects_already_verified() -> None:
    user = _unverified_user()
    user.email_confirmed_at = datetime.now(timezone.utc)
    db = AsyncMock()

    with pytest.raises(AppException) as exc_info:
        await verification_flow_service.continue_verification(db, user=user)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "VERIFICATION_ALREADY_COMPLETED"
