"""Unit tests for player home service."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.core.exceptions import AppException
from app.models.enums import UserRole
from app.models.user import User
from app.services import player_home as player_home_service
from tests.conftest import (
    TEST_PLACEHOLDER_HASH,
    UNVERIFIED_PLAYER_EMAIL,
    UNVERIFIED_PLAYER_ID,
)


def test_format_session_name_prefers_practice_plan() -> None:
    name = player_home_service._format_session_name(
        session_mode="one_drill",
        practice_plan_name="Morning Shooting Block",
        session_details=None,
    )
    assert name == "Morning Shooting Block"


def test_format_session_name_from_session_mode() -> None:
    name = player_home_service._format_session_name(
        session_mode="one_drill",
        practice_plan_name=None,
        session_details=None,
    )
    assert name == "One Drill"


def test_select_motivational_card_is_stable() -> None:
    player_id = UUID("00000000-0000-4000-8000-000000000033")
    first = player_home_service._select_motivational_card(player_id)
    second = player_home_service._select_motivational_card(player_id)
    assert first == second
    assert first in player_home_service.MOTIVATIONAL_QUOTES


@pytest.mark.asyncio
async def test_get_player_home_raises_404_without_roster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    user = User(
        id=UNVERIFIED_PLAYER_ID,
        email=UNVERIFIED_PLAYER_EMAIL,
        encrypted_password=TEST_PLACEHOLDER_HASH,
        role=UserRole.PLAYER.value,
        is_active=True,
    )

    async def _ensure_player_context(_db: object, _user: User) -> None:
        raise AppException(
            code="PLAYER_NOT_FOUND",
            message="Player not found",
            status_code=404,
        )

    monkeypatch.setattr(
        "app.services.player_home.player_identity.ensure_player_context",
        _ensure_player_context,
    )

    with pytest.raises(AppException) as exc_info:
        await player_home_service.get_player_home(db, user)
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "PLAYER_NOT_FOUND"
