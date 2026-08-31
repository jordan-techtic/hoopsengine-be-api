"""Resolve authenticated player users to client-domain roster records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.user import User
from app.services import client_db

PLAYERS_TABLE = "players"


@dataclass(frozen=True)
class PlayerContext:
    """Linked roster identity for an authenticated player user."""

    player_id: UUID
    org_id: UUID | None
    subteam_id: UUID | None
    row: dict[str, Any]


async def _column_exists(db: AsyncSession, table_name: str, column_name: str) -> bool:
    """Return True when a column exists on a public table."""
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND column_name = :column_name
            )
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return bool(exists)


def _player_context_from_row(mapping: dict[str, Any]) -> PlayerContext:
    """Build a PlayerContext from a players table row."""
    subteam_raw = mapping.get("subteam_id")
    org_raw = mapping.get("org_id")
    return PlayerContext(
        player_id=UUID(str(mapping["id"])),
        org_id=UUID(str(org_raw)) if org_raw is not None else None,
        subteam_id=UUID(str(subteam_raw)) if subteam_raw is not None else None,
        row=mapping,
    )


async def resolve_player_context(db: AsyncSession, user: User) -> PlayerContext | None:
    """
    Resolve the authenticated user to a ``players`` roster row.

    Prefers ``players.user_id`` when the column exists, then falls back to
    case-insensitive email match on ``players.email``.
    """
    if not await client_db.table_exists(db, PLAYERS_TABLE):
        return None

    has_user_id = await _column_exists(db, PLAYERS_TABLE, "user_id")
    has_email = await _column_exists(db, PLAYERS_TABLE, "email")
    has_subteam_id = await _column_exists(db, PLAYERS_TABLE, "subteam_id")
    subteam_select = "subteam_id" if has_subteam_id else "NULL AS subteam_id"

    if has_user_id:
        result = await db.execute(
            text(
                f"""
                SELECT id, org_id, {subteam_select},
                       first_name, last_name, jersey_number, email, user_id
                FROM players
                WHERE user_id = :user_id
                  AND COALESCE(active, true) = true
                LIMIT 1
                """
            ),
            {"user_id": user.id},
        )
        row = result.mappings().first()
        if row is not None:
            return _player_context_from_row(dict(row))

    if has_email and user.email:
        result = await db.execute(
            text(
                f"""
                SELECT id, org_id, {subteam_select},
                       first_name, last_name, jersey_number, email, user_id
                FROM players
                WHERE email ILIKE :email
                  AND COALESCE(active, true) = true
                LIMIT 1
                """
            ),
            {"email": user.email.strip()},
        )
        row = result.mappings().first()
        if row is not None:
            return _player_context_from_row(dict(row))

    return None


async def ensure_player_context(db: AsyncSession, user: User) -> PlayerContext:
    """Return linked roster context or raise 404 when no player record exists."""
    context = await resolve_player_context(db, user)
    if context is None:
        raise AppException(
            code="PLAYER_NOT_FOUND",
            message="Player not found",
            status_code=404,
            details=[
                {
                    "field": "player",
                    "message": "No roster profile is linked to this account",
                }
            ],
        )
    return context
