"""Unit tests for coach authentication service."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.config import settings
from app.models.enums import UserRole
from app.models.user import User
from app.services.auth import get_coach_by_identifier, login_coach


def _verified_coach(**overrides: object) -> User:
    now = datetime.now(timezone.utc)
    values: dict[str, object] = {
        "id": uuid4(),
        "email": "coach@example.com",
        "username": "coachuser",
        "encrypted_password": "$2b$12$test",
        "role": UserRole.COACH.value,
        "is_super_admin": False,
        "is_active": True,
        "email_confirmed_at": now,
        "created_at": now,
    }
    values.update(overrides)
    return User(**values)


def test_get_coach_by_identifier_email(monkeypatch: pytest.MonkeyPatch) -> None:
    coach = _verified_coach()

    async def fake_email(db: AsyncMock, email: str) -> User | None:
        assert email == "coach@example.com"
        return coach

    monkeypatch.setattr("app.services.auth.get_user_by_email", fake_email)

    async def _run() -> User | None:
        return await get_coach_by_identifier(AsyncMock(), "coach@example.com")

    assert asyncio.run(_run()) is coach


def test_get_coach_by_identifier_username(monkeypatch: pytest.MonkeyPatch) -> None:
    coach = _verified_coach()

    async def fake_username(db: AsyncMock, username: str) -> User | None:
        assert username == "coachuser"
        return coach

    monkeypatch.setattr("app.services.auth.get_user_by_username", fake_username)

    async def _run() -> User | None:
        return await get_coach_by_identifier(AsyncMock(), "coachuser")

    assert asyncio.run(_run()) is coach


def test_login_coach_rejects_unverified_email(monkeypatch: pytest.MonkeyPatch) -> None:
    coach = _verified_coach(email_confirmed_at=None)

    async def fake_lookup(db: AsyncMock, identifier: str) -> User | None:
        return coach

    monkeypatch.setattr("app.services.auth.get_coach_by_identifier", fake_lookup)
    monkeypatch.setattr("app.services.auth.verify_password", lambda _password, _hash: True)

    async def _run() -> object:
        return await login_coach(AsyncMock(), "coach@example.com", "Secret123!")

    assert asyncio.run(_run()) is None


def test_login_coach_remember_me_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    coach = _verified_coach()

    async def fake_lookup(db: AsyncMock, identifier: str) -> User | None:
        return coach

    monkeypatch.setattr("app.services.auth.get_coach_by_identifier", fake_lookup)
    monkeypatch.setattr("app.services.auth.verify_password", lambda _password, _hash: True)

    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda obj: obj)

    async def _run() -> int:
        result = await login_coach(
            db,
            "coach@example.com",
            "Secret123!",
            remember_me=True,
        )
        assert result is not None
        return result.expires_in_hours

    assert asyncio.run(_run()) == settings.REMEMBER_ME_TOKEN_EXPIRE_HOURS
