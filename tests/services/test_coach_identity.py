"""Unit tests for coach identity resolution."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import AppException
from app.services import coach_identity


def test_get_coach_org_id_returns_user_org_id() -> None:
    org_id = uuid4()
    user = MagicMock()
    user.org_id = org_id
    assert coach_identity.get_coach_org_id(user) == org_id


def test_resolve_recorder_coach_id_by_email() -> None:
    org_id = uuid4()
    coach_id = uuid4()
    user = MagicMock()
    user.org_id = org_id
    user.email = "coach@test.com"

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = coach_id
    db.execute = AsyncMock(return_value=result)

    resolved = asyncio.run(coach_identity.resolve_recorder_coach_id(db, user))
    assert resolved == coach_id


def test_ensure_recorder_context_requires_org() -> None:
    user = MagicMock()
    user.org_id = None
    db = AsyncMock()

    with pytest.raises(AppException) as exc_info:
        asyncio.run(coach_identity.ensure_recorder_context(db, user))
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"
