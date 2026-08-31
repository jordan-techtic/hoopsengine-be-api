"""Player invitation code verification service."""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.services import client_db

logger = logging.getLogger(__name__)

PLAYERS_TABLE = "players"
ORGANIZATIONS_TABLE = "organizations"
INVITATION_CODE_PATTERN = re.compile(r"^PC-[0-9A-F]{8}$")


def validate_invitation_code_format(invitation_code: str) -> str:
    """Return a trimmed invitation code or raise 400 when empty or invalid."""
    cleaned = (invitation_code or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Invitation code is required",
            status_code=400,
            details=[{"field": "invitation_code", "message": "Invitation code is required"}],
        )
    if not INVITATION_CODE_PATTERN.match(cleaned):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Invitation code must use PC-XXXXXXXX format (case sensitive)",
            status_code=400,
            details=[
                {
                    "field": "invitation_code",
                    "message": "Invitation code must use PC-XXXXXXXX format (case sensitive)",
                }
            ],
        )
    return cleaned


def _player_registration_link() -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/player/register"


async def verify_player_invitation_code(
    db: AsyncSession,
    invitation_code: str,
) -> dict[str, Any]:
    """
    Verify a player invitation code against the client players table.

    Case-sensitive exact match on ``player_code``. Raises 404 when not found.
    Raises 409 when the code was already redeemed (``user_id`` is set).
    """
    await client_db.require_table(db, PLAYERS_TABLE)
    cleaned = validate_invitation_code_format(invitation_code)

    has_user_id = await _column_exists(db, PLAYERS_TABLE, "user_id")
    user_id_select = "p.user_id" if has_user_id else "NULL AS user_id"

    org_join = ""
    org_name_select = "NULL AS org_name"
    if await client_db.table_exists(db, ORGANIZATIONS_TABLE):
        org_join = f"LEFT JOIN {ORGANIZATIONS_TABLE} o ON o.id = p.org_id"
        org_name_select = "o.name AS org_name"

    result = await db.execute(
        text(
            f"""
            SELECT
                p.id,
                p.org_id,
                p.player_code,
                p.first_name,
                p.last_name,
                {user_id_select},
                {org_name_select}
            FROM {PLAYERS_TABLE} p
            {org_join}
            WHERE p.player_code = :player_code
            LIMIT 1
            """
        ),
        {"player_code": cleaned},
    )
    row = result.mappings().first()
    if row is None:
        raise AppException(
            code="INVITATION_CODE_NOT_FOUND",
            message="We couldn't find a player invitation with that code",
            status_code=404,
            details=[
                {
                    "field": "invitation_code",
                    "message": "We couldn't find a player invitation with that code",
                }
            ],
        )

    if row.get("user_id") is not None:
        raise AppException(
            code="INVITATION_ALREADY_REDEEMED",
            message="This invitation code has already been used",
            status_code=409,
            details=[
                {
                    "field": "invitation_code",
                    "message": "This invitation code has already been used",
                }
            ],
        )

    player_id = UUID(str(row["id"]))
    org_id = UUID(str(row["org_id"])) if row.get("org_id") is not None else None
    player_code = str(row["player_code"])
    org_name = row.get("org_name")

    logger.info("Verified player invitation code for player %s", player_id)

    return {
        "message": "Invitation code verified successfully",
        "status": "verified",
        "description": "Continue registration to link this invitation to your account",
        "link": _player_registration_link(),
        "title": "Player Code Verification",
        "organization": org_name,
        "code": player_code,
        "verification_code": player_code,
        "id": player_id,
        "player_id": player_id,
        "org_id": org_id,
        "player_code": player_code,
    }


async def _column_exists(db: AsyncSession, table_name: str, column_name: str) -> bool:
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
