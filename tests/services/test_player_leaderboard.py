"""Unit tests for authenticated player leaderboard service."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.core.exceptions import AppException
from app.models.enums import UserRole
from app.models.user import User
from app.services import player_leaderboard as player_leaderboard_service
from tests.conftest import SEEDED_ORG_ID, TEST_PLACEHOLDER_HASH, VIEWER_EMAIL, VIEWER_ID


def _viewer_user() -> User:
    return User(
        id=VIEWER_ID,
        email=VIEWER_EMAIL,
        encrypted_password=TEST_PLACEHOLDER_HASH,
        role=UserRole.PLAYER.value,
        is_active=True,
        org_id=SEEDED_ORG_ID,
    )


@pytest.mark.asyncio
async def test_search_raises_404_when_no_players_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()

    async def _resolve_org(_db: object, _user: User) -> UUID:
        return SEEDED_ORG_ID

    async def _empty_items(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(
        player_leaderboard_service,
        "resolve_leaderboard_org_id",
        _resolve_org,
    )
    monkeypatch.setattr(
        "app.services.player_leaderboard.leaderboard_service._aggregate_player_stats",
        _empty_items,
    )

    with pytest.raises(AppException) as exc_info:
        await player_leaderboard_service.search_authenticated_leaderboard(
            db,
            _viewer_user(),
            search_query="Jane",
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "PLAYERS_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_leaderboard_raises_400_on_empty_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()

    async def _resolve_org(_db: object, _user: User) -> UUID:
        return SEEDED_ORG_ID

    monkeypatch.setattr(
        player_leaderboard_service,
        "resolve_leaderboard_org_id",
        _resolve_org,
    )

    with pytest.raises(AppException) as exc_info:
        await player_leaderboard_service.get_authenticated_leaderboard(
            db,
            _viewer_user(),
            search_query="",
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"
