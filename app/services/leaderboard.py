"""Leaderboard aggregation, search, and filter logic."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.enums import LeaderboardFilterMetric
from app.models.user import User
from app.services import client_db
from app.services.session_summary import compute_shooting_percent

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 50
ORDER_BY_METRIC = {
    LeaderboardFilterMetric.SHOOTING_PERCENT: (
        lambda item: (-item["shooting_percent"], -item["attempts"], item["full_name"])
    ),
    LeaderboardFilterMetric.ATTEMPTS: (
        lambda item: (-item["attempts"], -item["shooting_percent"], item["full_name"])
    ),
    LeaderboardFilterMetric.MAKES: (
        lambda item: (-item["makes"], -item["shooting_percent"], item["full_name"])
    ),
}


def resolve_search_text(
    *,
    search_query: str | None,
    full_name: str | None,
) -> str:
    """Return normalized search text or raise 400 when both inputs are empty."""
    candidate = (search_query or full_name or "").strip()
    if not candidate:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Search query is required",
            status_code=400,
            details=[
                {
                    "field": "search_query",
                    "message": "Provide search_query or full_name to search players",
                }
            ],
        )
    return candidate


def _build_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert aggregated SQL rows into leaderboard item dictionaries."""
    items: list[dict[str, Any]] = []
    for row in rows:
        full_name = str(row["full_name"]).strip() or "Unknown Player"
        player_id = UUID(str(row["player_id"]))
        attempts = int(row["attempts"] or 0)
        makes = int(row["makes"] or 0)
        items.append(
            {
                "id": player_id,
                "name": full_name,
                "full_name": full_name,
                "shooting_percent": compute_shooting_percent(makes, attempts),
                "attempts": attempts,
                "makes": makes,
            }
        )
    return items


def _rank_items(
    items: list[dict[str, Any]],
    metric: LeaderboardFilterMetric,
) -> list[dict[str, Any]]:
    """Sort items by metric and assign 1-based ranks."""
    sort_key = ORDER_BY_METRIC[metric]
    sorted_items = sorted(items, key=sort_key)
    ranked: list[dict[str, Any]] = []
    for index, item in enumerate(sorted_items, start=1):
        ranked.append({"rank": index, **item})
    return ranked


def _build_list_response(
    items: list[dict[str, Any]],
    *,
    message: str,
    description: str,
) -> dict[str, Any]:
    """Shape a leaderboard list response for the API layer."""
    return {
        "success": True,
        "message": message,
        "description": description,
        "link": None,
        "error": None,
        "items": items,
    }


async def _aggregate_player_stats(
    db: AsyncSession,
    *,
    org_id: UUID | None = None,
    search_term: str | None = None,
    sort_metric: LeaderboardFilterMetric = LeaderboardFilterMetric.SHOOTING_PERCENT,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Aggregate player stats from session_data joined with players."""
    if not await client_db.table_exists(db, "session_data"):
        return []
    if not await client_db.table_exists(db, "players"):
        return []

    filters = ["1=1"]
    params: dict[str, Any] = {}

    if org_id is not None:
        filters.append("p.org_id = :org_id")
        params["org_id"] = org_id

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
    query = f"""
        SELECT
            p.id AS player_id,
            TRIM(COALESCE(p.first_name, '') || ' ' || COALESCE(p.last_name, '')) AS full_name,
            COALESCE(SUM(sd.attempts), 0) AS attempts,
            COALESCE(SUM(sd.makes), 0) AS makes
        FROM players p
        LEFT JOIN session_data sd ON sd.player_id = p.id
        WHERE {where_sql}
        GROUP BY p.id, p.first_name, p.last_name
    """

    result = await db.execute(text(query), params)
    rows = [dict(row) for row in result.mappings().all()]
    items = _build_items(rows)
    return _rank_items(items, sort_metric)[:limit]


async def get_leaderboard(
    db: AsyncSession,
    *,
    org_id: UUID | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return publicly visible leaderboard rankings."""
    items = await _aggregate_player_stats(
        db,
        org_id=org_id,
        sort_metric=LeaderboardFilterMetric.SHOOTING_PERCENT,
        limit=limit,
    )
    return _build_list_response(
        items,
        message="Leaderboard loaded successfully",
        description="Top players ranked by shooting percentage",
    )


async def search_players(
    db: AsyncSession,
    user: User,
    *,
    search_query: str | None,
    full_name: str | None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Search players by name within the authenticated coach's organization."""
    term = resolve_search_text(search_query=search_query, full_name=full_name)
    org_id = user.org_id
    items = await _aggregate_player_stats(
        db,
        org_id=org_id,
        search_term=term,
        sort_metric=LeaderboardFilterMetric.SHOOTING_PERCENT,
        limit=limit,
    )
    logger.info("Leaderboard search for coach %s returned %s players", user.id, len(items))
    return _build_list_response(
        items,
        message="Leaderboard search completed successfully",
        description=f"Players matching '{term}'",
    )


async def filter_leaderboard(
    db: AsyncSession,
    user: User,
    *,
    filter_metric: LeaderboardFilterMetric,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return leaderboard rows sorted by the selected performance metric."""
    org_id = user.org_id
    items = await _aggregate_player_stats(
        db,
        org_id=org_id,
        sort_metric=filter_metric,
        limit=limit,
    )
    return _build_list_response(
        items,
        message="Leaderboard filtered successfully",
        description=f"Players ranked by {filter_metric.value.replace('_', ' ')}",
    )
