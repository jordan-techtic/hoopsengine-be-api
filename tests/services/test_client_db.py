"""Unit tests for client_db helpers."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import AppException
from app.services import client_db


def test_table_exists_true() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=True)
    assert asyncio.run(client_db.table_exists(db, "practice_sessions")) is True


def test_require_table_raises_when_missing() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=False)
    with pytest.raises(AppException) as exc_info:
        asyncio.run(client_db.require_table(db, "practice_sessions"))
    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "CLIENT_TABLE_UNAVAILABLE"
