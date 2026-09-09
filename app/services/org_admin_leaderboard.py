"""Organization admin leaderboard aggregation, search, and filter logic (HE-404)."""

from __future__ import annotations

import logging
import re
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.enums import LeaderboardFilterMetric
from app.models.user import User
from app.schemas.org_admin_leaderboard import (
    OrgAdminLeaderboardFilterDateRange,
    OrgAdminLeaderboardFilters,
)
from app.services import client_db
from app.services import leaderboard as leaderboard_service
from app.services.org_admin_profile import require_admin_organization

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = leaderboard_service.DEFAULT_LIMIT


def validate_optional_phone(phone: str | None) -> None:
    """Validate optional Figma status-bar phone metadata when provided."""
    if phone is None or not phone.strip():
        return
    cleaned = phone.strip()
    if len(cleaned) > 30:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Phone number is invalid",
            status_code=400,
            details=[{"field": "phone", "message": "Phone number is invalid"}],
        )
    if not re.sub(r"\D", "", cleaned):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Phone number must contain at least one digit",
            status_code=400,
            details=[{"field": "phone", "message": "Phone number must contain at least one digit"}],
        )


def _apply_ranking_direction(
    items: list[dict[str, Any]],
    *,
    ranking: Literal["top", "bottom"],
) -> list[dict[str, Any]]:
    """Return ranked items ordered for top or bottom performer views."""
    if ranking == "bottom":
        reversed_items = list(reversed(items))
        return [{"rank": index, **{key: value for key, value in item.items() if key != "rank"}}
                for index, item in enumerate(reversed_items, start=1)]
    return items


def _build_org_response(
    items: list[dict[str, Any]],
    *,
    organization_name: str,
    message: str,
    description: str,
    phone: str | None = None,
) -> dict[str, Any]:
    """Shape a leaderboard list response with organization context for org admins."""
    result = leaderboard_service._build_list_response(
        items,
        message=message,
        description=description,
    )
    result["organization"] = organization_name
    result["phone"] = phone
    return result


async def _aggregate_org_player_stats(
    db: AsyncSession,
    *,
    org_id: UUID,
    search_term: str | None = None,
    date_range: OrgAdminLeaderboardFilterDateRange | None = None,
    sort_metric: LeaderboardFilterMetric = LeaderboardFilterMetric.SHOOTING_PERCENT,
    ranking: Literal["top", "bottom"] = "top",
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Aggregate player stats for an organization with optional search and date filters."""
    if not await client_db.table_exists(db, "session_data"):
        return []
    if not await client_db.table_exists(db, "players"):
        return []

    filters = ["p.org_id = :org_id"]
    params: dict[str, Any] = {"org_id": org_id}

    if search_term:
        filters.append(
            """
            (
                p.first_name ILIKE :search_pattern
                OR p.last_name ILIKE :search_pattern
                OR TRIM(COALESCE(p.first_name, '') || ' ' || COALESCE(p.last_name, '')) ILIKE :search_pattern
            )
            """
        )
        params["search_pattern"] = f"%{search_term.strip()}%"

    where_sql = " AND ".join(filters)
    if date_range is not None:
        params["date_start"] = date_range.start
        params["date_end"] = date_range.end
        if await client_db.table_exists(db, "practice_sessions"):
            session_source = """
                LEFT JOIN (
                    SELECT
                        sd.player_id,
                        sd.attempts,
                        sd.makes
                    FROM session_data sd
                    LEFT JOIN practice_sessions ps ON ps.id = sd.session_id
                    WHERE COALESCE(
                        CAST(ps.started_at AS date),
                        CAST(ps.created_at AS date),
                        sd.session_date
                    ) >= :date_start
                      AND COALESCE(
                        CAST(ps.started_at AS date),
                        CAST(ps.created_at AS date),
                        sd.session_date
                    ) <= :date_end
                ) sd ON sd.player_id = p.id
            """
        else:
            session_source = """
                LEFT JOIN (
                    SELECT player_id, attempts, makes
                    FROM session_data
                    WHERE session_date >= :date_start
                      AND session_date <= :date_end
                ) sd ON sd.player_id = p.id
            """
    else:
        session_source = "LEFT JOIN session_data sd ON sd.player_id = p.id"

    query = f"""
        SELECT
            p.id AS player_id,
            TRIM(COALESCE(p.first_name, '') || ' ' || COALESCE(p.last_name, '')) AS full_name,
            COALESCE(SUM(sd.attempts), 0) AS attempts,
            COALESCE(SUM(sd.makes), 0) AS makes
        FROM players p
        {session_source}
        WHERE {where_sql}
        GROUP BY p.id, p.first_name, p.last_name
    """

    result = await db.execute(text(query), params)
    rows = [dict(row) for row in result.mappings().all()]
    items = leaderboard_service._build_items(rows)
    ranked = leaderboard_service._rank_items(items, sort_metric)
    directed = _apply_ranking_direction(ranked, ranking=ranking)
    return directed[:limit]


async def get_org_admin_leaderboard(
    db: AsyncSession,
    user: User,
    *,
    phone: str | None = None,
) -> dict[str, Any]:
    """Return org-scoped leaderboard rankings for an organization admin."""
    validate_optional_phone(phone)
    organization = await require_admin_organization(db, user)
    items = await _aggregate_org_player_stats(
        db,
        org_id=organization.id,
        sort_metric=LeaderboardFilterMetric.SHOOTING_PERCENT,
        ranking="top",
    )
    logger.info(
        "Loaded org-admin leaderboard for user %s (%s rows)",
        user.id,
        len(items),
    )
    return _build_org_response(
        items,
        organization_name=organization.name,
        message="Leaderboard loaded successfully",
        description="Top players ranked by shooting percentage",
        phone=phone,
    )


async def search_org_admin_leaderboard(
    db: AsyncSession,
    user: User,
    *,
    search_query: str | None,
    full_name: str | None,
    phone: str | None = None,
) -> dict[str, Any]:
    """Search players by name within the organization admin's organization."""
    validate_optional_phone(phone)
    term = leaderboard_service.resolve_search_text(
        search_query=search_query,
        full_name=full_name,
    )
    organization = await require_admin_organization(db, user)
    items = await _aggregate_org_player_stats(
        db,
        org_id=organization.id,
        search_term=term,
        sort_metric=LeaderboardFilterMetric.SHOOTING_PERCENT,
        ranking="top",
    )
    logger.info(
        "Org-admin leaderboard search for user %s returned %s players",
        user.id,
        len(items),
    )
    return _build_org_response(
        items,
        organization_name=organization.name,
        message="Leaderboard search completed successfully",
        description=f"Players matching '{term}'",
        phone=phone,
    )


async def filter_org_admin_leaderboard(
    db: AsyncSession,
    user: User,
    *,
    filters: OrgAdminLeaderboardFilters,
    full_name: str | None = None,
    phone: str | None = None,
) -> dict[str, Any]:
    """Return leaderboard rows filtered by ranking direction and optional date range."""
    validate_optional_phone(phone)
    organization = await require_admin_organization(db, user)
    items = await _aggregate_org_player_stats(
        db,
        org_id=organization.id,
        date_range=filters.date_range,
        sort_metric=LeaderboardFilterMetric.SHOOTING_PERCENT,
        ranking=filters.ranking,
    )
    ranking_label = "top" if filters.ranking == "top" else "bottom"
    description = f"Players ranked by shooting percentage ({ranking_label} performers)"
    if filters.date_range is not None:
        description = (
            f"{description} between {filters.date_range.start.isoformat()} "
            f"and {filters.date_range.end.isoformat()}"
        )
    logger.info(
        "Org-admin leaderboard filter for user %s returned %s players",
        user.id,
        len(items),
    )
    return _build_org_response(
        items,
        organization_name=organization.name,
        message="Leaderboard filtered successfully",
        description=description,
        phone=phone,
    )
