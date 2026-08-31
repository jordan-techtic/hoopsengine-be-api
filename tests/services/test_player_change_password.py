"""Unit tests for player change-password service."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import AppException
from app.core.security import hash_password
from app.models.user import User
from app.services import player_change_password as player_change_password_service
from tests.conftest import (
    TEST_CURRENT_PASSWORD,
    TEST_DIFFERENT_PASSWORD,
    TEST_INVALID_PASSWORD,
    TEST_NEW_SECURE_PASSWORD,
    TEST_VALID_PASSWORD,
)


def _player_user(password: str = TEST_VALID_PASSWORD) -> User:
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
    user = _player_user(TEST_CURRENT_PASSWORD)
    result = await player_change_password_service.change_player_password(
        db,
        user,
        current_password=TEST_CURRENT_PASSWORD,
        new_password=TEST_NEW_SECURE_PASSWORD,
        confirm_new_password=TEST_NEW_SECURE_PASSWORD,
    )
    assert result is user
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_change_player_password_mismatch_raises_409() -> None:
    db = AsyncMock()
    user = _player_user(TEST_CURRENT_PASSWORD)
    with pytest.raises(AppException) as exc_info:
        await player_change_password_service.change_player_password(
            db,
            user,
            current_password=TEST_CURRENT_PASSWORD,
            new_password=TEST_NEW_SECURE_PASSWORD,
            confirm_new_password=TEST_DIFFERENT_PASSWORD,
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "PASSWORD_MISMATCH"


@pytest.mark.asyncio
async def test_change_player_password_wrong_current_raises_400() -> None:
    db = AsyncMock()
    user = _player_user(TEST_CURRENT_PASSWORD)
    with pytest.raises(AppException) as exc_info:
        await player_change_password_service.change_player_password(
            db,
            user,
            current_password=TEST_INVALID_PASSWORD,
            new_password=TEST_NEW_SECURE_PASSWORD,
            confirm_new_password=TEST_NEW_SECURE_PASSWORD,
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"
