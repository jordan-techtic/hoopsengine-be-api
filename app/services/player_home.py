"""Business logic for authenticated player Home Screen APIs."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user import User
from app.services import client_db, player_identity, player_progress
from app.services.session_summary import FREE_THROW_CATEGORY_PATTERN

logger = logging.getLogger(__name__)

SESSION_DATA_TABLE = "session_data"
PRACTICE_SESSIONS_TABLE = "practice_sessions"
DRILLS_TABLE = "drills"
TEAMS_TABLE = "teams"
PRACTICE_PLANS_TABLE = "practice_plans"

MOTIVATIONAL_QUOTES: tuple[str, ...] = (
    "Earn your minutes. Own your moment.",
    "Consistency beats talent when talent stops showing up.",
    "Every rep is a vote for the player you want to become.",
    "Focus on the process. The results will follow.",
    "Show up ready. Leave better than you arrived.",
)


def _player_display_name(row: dict[str, Any]) -> str:
    """Return a display name from a players row."""
    first = (row.get("first_name") or "").strip()
    last = (row.get("last_name") or "").strip()
    return " ".join(part for part in (first, last) if part).strip() or "Player"


def _format_session_name(
    *,
    session_mode: str | None,
    practice_plan_name: str | None,
    session_details: Any,
) -> str:
    """Derive a user-facing session name for recent session cards."""
    if practice_plan_name and practice_plan_name.strip():
        return practice_plan_name.strip()

    details = session_details
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except json.JSONDecodeError:
            details = None
    if isinstance(details, dict):
        for key in ("name", "session_name", "title", "description"):
            value = details.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    mode = (session_mode or "").strip()
    if mode:
        return mode.replace("_", " ").title()
    return "Training Session"


def _select_motivational_card(player_id: UUID) -> str:
    """Return a stable motivational quote for the player."""
    index = int.from_bytes(player_id.bytes[-2:], "big") % len(MOTIVATIONAL_QUOTES)
    return MOTIVATIONAL_QUOTES[index]


async def _load_player_team_name(
    db: AsyncSession,
    *,
    team_id: UUID | None,
    org_id: UUID | None,
) -> str:
    """Resolve the team display name, falling back to the organization name."""
    if team_id is not None and await client_db.table_exists(db, TEAMS_TABLE):
        result = await db.execute(
            text(
                """
                SELECT name
                FROM teams
                WHERE id = :team_id
                LIMIT 1
                """
            ),
            {"team_id": team_id},
        )
        row = result.mappings().first()
        if row is not None:
            name = str(row["name"]).strip()
            if name:
                return name

    if org_id is not None:
        result = await db.execute(select(Organization).where(Organization.id == org_id))
        org = result.scalar_one_or_none()
        if org is not None and org.name:
            return org.name

    return "Team"


async def _load_player_details(db: AsyncSession, player_id: UUID) -> dict[str, Any]:
    """Load extended roster fields needed for the home screen."""
    if not await client_db.table_exists(db, player_identity.PLAYERS_TABLE):
        return {}

    result = await db.execute(
        text(
            """
            SELECT id, org_id, team_id, first_name, last_name, jersey_number
            FROM players
            WHERE id = :player_id
              AND COALESCE(active, true) = true
            LIMIT 1
            """
        ),
        {"player_id": player_id},
    )
    row = result.mappings().first()
    return dict(row) if row is not None else {}


async def _load_recent_sessions(
    db: AsyncSession,
    player_id: UUID,
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Build recent session cards for the player home screen."""
    if not await client_db.table_exists(db, SESSION_DATA_TABLE):
        return []

    joins_practice_sessions = await client_db.table_exists(db, PRACTICE_SESSIONS_TABLE)
    joins_practice_plans = await client_db.table_exists(db, PRACTICE_PLANS_TABLE)

    if joins_practice_sessions:
        plan_join = ""
        plan_select = "NULL AS practice_plan_name"
        if joins_practice_plans:
            plan_join = "LEFT JOIN practice_plans pp ON pp.id = ps.practice_plan_id"
            plan_select = "pp.name AS practice_plan_name"

        query = f"""
            SELECT
                ps.session_mode,
                ps.session_details,
                {plan_select},
                COALESCE(ps.started_at, ps.created_at, sd.session_date) AS session_when,
                COALESCE(
                    SUM(
                        CASE
                            WHEN d.category IS NOT NULL
                                 AND LOWER(d.category) LIKE :free_throw_pattern
                            THEN 0
                            ELSE sd.makes
                        END
                    ),
                    0
                ) AS makes,
                COALESCE(
                    SUM(
                        CASE
                            WHEN d.category IS NOT NULL
                                 AND LOWER(d.category) LIKE :free_throw_pattern
                            THEN 0
                            ELSE sd.attempts
                        END
                    ),
                    0
                ) AS attempts
            FROM session_data sd
            JOIN practice_sessions ps ON ps.id = sd.session_id
            {plan_join}
            LEFT JOIN drills d ON d.id = sd.drill_id
            WHERE sd.player_id = :player_id
            GROUP BY ps.id, ps.session_mode, ps.session_details, practice_plan_name,
                     ps.started_at, ps.created_at, sd.session_date
            ORDER BY session_when DESC NULLS LAST
            LIMIT :limit
        """
    else:
        query = """
            SELECT
                NULL AS session_mode,
                NULL AS session_details,
                NULL AS practice_plan_name,
                sd.session_date AS session_when,
                COALESCE(
                    SUM(
                        CASE
                            WHEN d.category IS NOT NULL
                                 AND LOWER(d.category) LIKE :free_throw_pattern
                            THEN 0
                            ELSE sd.makes
                        END
                    ),
                    0
                ) AS makes,
                COALESCE(
                    SUM(
                        CASE
                            WHEN d.category IS NOT NULL
                                 AND LOWER(d.category) LIKE :free_throw_pattern
                            THEN 0
                            ELSE sd.attempts
                        END
                    ),
                    0
                ) AS attempts
            FROM session_data sd
            LEFT JOIN drills d ON d.id = sd.drill_id
            WHERE sd.player_id = :player_id
            GROUP BY sd.session_id, sd.session_date
            ORDER BY session_when DESC NULLS LAST
            LIMIT :limit
        """

    result = await db.execute(
        text(query),
        {
            "player_id": player_id,
            "free_throw_pattern": FREE_THROW_CATEGORY_PATTERN,
            "limit": limit,
        },
    )

    sessions: list[dict[str, Any]] = []
    for row in result.mappings().all():
        mapping = dict(row)
        makes = int(mapping.get("makes") or 0)
        attempts = int(mapping.get("attempts") or 0)
        sessions.append(
            {
                "session_name": _format_session_name(
                    session_mode=str(mapping.get("session_mode") or ""),
                    practice_plan_name=(
                        str(mapping["practice_plan_name"])
                        if mapping.get("practice_plan_name") is not None
                        else None
                    ),
                    session_details=mapping.get("session_details"),
                ),
                "attempts": attempts,
                "fg_percentage": player_progress.format_progress_shooting_percentage(makes, attempts),
            }
        )
    return sessions


async def get_player_home(
    db: AsyncSession,
    user: User,
    *,
    phone: str | None = None,
    company: str | None = None,
) -> dict[str, Any]:
    """Return aggregated home screen data for the authenticated player."""
    context = await player_identity.ensure_player_context(db, user)
    player_row = {**context.row, **await _load_player_details(db, context.player_id)}
    if not player_row:
        player_row = context.row

    display_name = _player_display_name(player_row)
    team_id = player_row.get("team_id")
    org_id = context.org_id
    if team_id is not None and not isinstance(team_id, UUID):
        team_id = UUID(str(team_id))

    team_name = await _load_player_team_name(db, team_id=team_id, org_id=org_id)
    jersey_number = str(player_row.get("jersey_number") or "").strip() or "0"

    _, total_attempts, total_sessions = await player_progress._aggregate_field_goal_stats(
        db,
        context.player_id,
    )
    recent_sessions = await _load_recent_sessions(db, context.player_id, limit=3)
    motivational_card = _select_motivational_card(context.player_id)

    profile = {
        "user_name": display_name,
        "team_name": team_name,
        "jersey_number": jersey_number,
    }

    logger.info("Loaded player home data for user %s player %s", user.id, context.player_id)
    return {
        "success": True,
        "message": "Player home loaded successfully",
        "status": "ready",
        "description": None,
        "link": None,
        "error": None,
        "title": "Home",
        "id": context.player_id,
        "name": display_name,
        "profile": profile,
        "user_name": display_name,
        "team_name": team_name,
        "jersey_number": jersey_number,
        "total_sessions": total_sessions,
        "total_attempts": total_attempts,
        "recent_sessions": recent_sessions,
        "motivational_card": motivational_card,
        "phone": phone,
        "company": company or team_name,
    }
