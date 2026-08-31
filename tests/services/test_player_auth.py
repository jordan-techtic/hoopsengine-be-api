"""Unit tests for player authentication service."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.exceptions import AppException
from app.models.enums import UserRole
from app.models.user import User
from app.services import player_auth as player_auth_service


def _verified_player(**overrides: object) -> User:
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


def test_validate_login_fields_success() -> None:
    result = player_auth_service.validate_login_fields(
        email="player@example.com",
        password="Secret123!",
    )
    assert result["valid"] is True
    assert result["title"] == "LOGIN"


def test_validate_login_fields_missing_password() -> None:
    result = player_auth_service.validate_login_fields(
        email="player@example.com",
        password="",
    )
    assert result["valid"] is False
    assert any(error["field"] == "password" for error in result["errors"])


def test_validate_identifier_format_invalid_email() -> None:
    errors = player_auth_service.validate_identifier_format("not-an-email")
    assert errors
    assert errors[0]["field"] == "email"


@pytest.mark.asyncio
async def test_login_player_unknown_account_raises_401() -> None:
    db = AsyncMock()

    with patch(
        "app.services.player_auth.get_player_by_identifier",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(AppException) as exc_info:
            await player_auth_service.login_player(db, "player@example.com", "Secret123!")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_login_player_duplicate_session_raises_409() -> None:
    player = _verified_player(
        raw_user_meta_data={
            "active_session_jti": "existing-jti",
            "active_session_exp": (datetime.now(timezone.utc).replace(year=2099)).isoformat(),
        }
    )
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch(
        "app.services.player_auth.get_player_by_identifier",
        new=AsyncMock(return_value=player),
    ):
        with patch("app.services.player_auth.verify_password", return_value=True):
            with patch(
                "app.services.player_auth._has_active_session",
                new=AsyncMock(return_value=True),
            ):
                with pytest.raises(AppException) as exc_info:
                    await player_auth_service.login_player(
                        db,
                        "player@example.com",
                        "Secret123!",
                    )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "DUPLICATE_SESSION"


@pytest.mark.asyncio
async def test_login_player_remember_me_expiry() -> None:
    player = _verified_player()
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda obj: obj)

    with patch(
        "app.services.player_auth.get_player_by_identifier",
        new=AsyncMock(return_value=player),
    ):
        with patch("app.services.player_auth.verify_password", return_value=True):
            with patch(
                "app.services.player_auth._has_active_session",
                new=AsyncMock(return_value=False),
            ):
                result = await player_auth_service.login_player(
                    db,
                    "player@example.com",
                    "Secret123!",
                    remember_me=True,
                )

    assert result.expires_in_hours == settings.REMEMBER_ME_TOKEN_EXPIRE_HOURS
