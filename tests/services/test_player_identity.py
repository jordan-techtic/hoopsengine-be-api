"""Unit tests for player identity resolution."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.core.exceptions import AppException
from app.models.enums import UserRole
from app.models.user import User
from app.services import player_identity as player_identity_service
from app.services.player_identity import _player_context_from_row
from tests.conftest import TEST_PLACEHOLDER_HASH, VIEWER_EMAIL, VIEWER_ID


def _viewer_user() -> User:
    return User(
        id=VIEWER_ID,
        email=VIEWER_EMAIL,
        encrypted_password=TEST_PLACEHOLDER_HASH,
        role=UserRole.PLAYER.value,
        is_active=True,
    )


def test_player_context_from_row_includes_subteam_id() -> None:
    context = _player_context_from_row(
        {
            "id": "00000000-0000-4000-8000-000000000039",
            "org_id": "00000000-0000-4000-8000-000000000010",
            "subteam_id": "00000000-0000-4000-8000-000000000040",
            "first_name": "Viewer",
            "last_name": "Player",
        }
    )
    assert context.player_id == UUID("00000000-0000-4000-8000-000000000039")
    assert context.org_id == UUID("00000000-0000-4000-8000-000000000010")
    assert context.subteam_id == UUID("00000000-0000-4000-8000-000000000040")


def test_player_context_from_row_handles_missing_subteam() -> None:
    context = _player_context_from_row(
        {
            "id": "00000000-0000-4000-8000-000000000039",
            "org_id": "00000000-0000-4000-8000-000000000010",
            "subteam_id": None,
            "first_name": "Viewer",
            "last_name": "Player",
        }
    )
    assert context.subteam_id is None


@pytest.mark.asyncio
async def test_ensure_player_context_raises_404_when_unlinked(monkeypatch: pytest.MonkeyPatch) -> None:
    db = AsyncMock()

    async def _table_exists(_db: object, _name: str) -> bool:
        return True

    async def _column_exists(_db: object, _table: str, _column: str) -> bool:
        return True

    async def _empty_result(*_args: object, **_kwargs: object) -> MagicMock:
        result = MagicMock()
        result.mappings.return_value.first.return_value = None
        return result

    monkeypatch.setattr("app.services.player_identity.client_db.table_exists", _table_exists)
    monkeypatch.setattr(player_identity_service, "_column_exists", _column_exists)
    db.execute = AsyncMock(side_effect=_empty_result)

    with pytest.raises(AppException) as exc_info:
        await player_identity_service.ensure_player_context(db, _viewer_user())

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "PLAYER_NOT_FOUND"


@pytest.mark.asyncio
async def test_resolve_player_context_by_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    db = AsyncMock()
    player_id = UUID("00000000-0000-4000-8000-000000000033")

    async def _table_exists(_db: object, _name: str) -> bool:
        return True

    async def _column_exists(_db: object, _table: str, column: str) -> bool:
        return column == "user_id"

    result = MagicMock()
    result.mappings.return_value.first.return_value = {
        "id": player_id,
        "org_id": UUID("00000000-0000-4000-8000-000000000010"),
        "subteam_id": None,
        "first_name": "Jane",
        "last_name": "Doe",
    }

    monkeypatch.setattr("app.services.player_identity.client_db.table_exists", _table_exists)
    monkeypatch.setattr(player_identity_service, "_column_exists", _column_exists)
    db.execute = AsyncMock(return_value=result)

    context = await player_identity_service.resolve_player_context(db, _viewer_user())

    assert context is not None
    assert context.player_id == player_id
