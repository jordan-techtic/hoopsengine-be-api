"""Unit tests for player reset password service."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import AppException
from app.models.enums import UserRole
from app.models.user import User
from app.services import player_reset_password as player_reset_password_service


def _player_user(**overrides: object) -> User:
    now = datetime.now(timezone.utc)
    values: dict[str, object] = {
        "id": uuid4(),
        "email": "player@example.com",
        "username": "playeruser",
        "encrypted_password": "$2b$12$test",
        "role": UserRole.PLAYER.value,
        "is_super_admin": False,
        "is_active": True,
        "email_confirmed_at": now,
        "created_at": now,
    }
    values.update(overrides)
    return User(**values)


@pytest.mark.asyncio
async def test_reset_player_password_delegates_without_phone() -> None:
    user = _player_user()
    db = AsyncMock()

    with patch(
        "app.services.player_reset_password.password_reset_service.reset_authenticated_password",
        new=AsyncMock(return_value=user),
    ) as reset_mock:
        result = await player_reset_password_service.reset_player_password(
            db,
            user=user,
            new_password="StrongPassword123!",
            confirm_password="StrongPassword123!",
        )

    assert result is user
    reset_mock.assert_awaited_once_with(
        db,
        user=user,
        new_password="StrongPassword123!",
        confirm_password="StrongPassword123!",
        phone=None,
    )


@pytest.mark.asyncio
async def test_reset_player_password_propagates_validation_error() -> None:
    user = _player_user()
    db = AsyncMock()

    with patch(
        "app.services.player_reset_password.password_reset_service.reset_authenticated_password",
        new=AsyncMock(
            side_effect=AppException(
                code="VALIDATION_ERROR",
                message="Passwords do not match",
                status_code=400,
            )
        ),
    ):
        with pytest.raises(AppException) as exc_info:
            await player_reset_password_service.reset_player_password(
                db,
                user=user,
                new_password="StrongPassword123!",
                confirm_password="Different456!",
            )

    assert exc_info.value.status_code == 400
