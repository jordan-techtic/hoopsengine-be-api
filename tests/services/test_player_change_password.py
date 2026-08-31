"""Unit tests for player change-password service."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import AppException
from app.core.security import hash_password
from app.models.user import User
from app.services import player_change_password as player_change_password_service


def _player_user(password: str = "StrongPassword123!") -> User:
    return User(
        email="player@example.com",
        encrypted_password=hash_password(password),
        role="player",
        is_super_admin=False,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_change_player_password_success() -> None:
    db = AsyncMock()
    user = _player_user("CurrentPass123!")
    result = await player_change_password_service.change_player_password(
        db,
        user,
        current_password="CurrentPass123!",
        new_password="NewSecure456!",
        confirm_new_password="NewSecure456!",
    )
    assert result is user
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_change_player_password_mismatch_raises_409() -> None:
    db = AsyncMock()
    user = _player_user("CurrentPass123!")
    with pytest.raises(AppException) as exc_info:
        await player_change_password_service.change_player_password(
            db,
            user,
            current_password="CurrentPass123!",
            new_password="NewSecure456!",
            confirm_new_password="Different456!",
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "PASSWORD_MISMATCH"


@pytest.mark.asyncio
async def test_change_player_password_wrong_current_raises_400() -> None:
    db = AsyncMock()
    user = _player_user("CurrentPass123!")
    with pytest.raises(AppException) as exc_info:
        await player_change_password_service.change_player_password(
            db,
            user,
            current_password="WrongPass123!",
            new_password="NewSecure456!",
            confirm_new_password="NewSecure456!",
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"
