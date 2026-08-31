"""Authenticated player leaderboard access, search, and org scoping."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.enums import LeaderboardFilterMetric, UserRole
from app.models.user import User
from app.services import leaderboard as leaderboard_service
from app.services import player_identity

logger = logging.getLogger(__name__)


async def resolve_leaderboard_org_id(db: AsyncSession, user: User) -> UUID | None:
    """Resolve the organization scope for leaderboard queries."""
    if user.org_id is not None:
        return user.org_id
    if user.role == UserRole.PLAYER.value:
        context = await player_identity.resolve_player_context(db, user)
        if context is not None:
            return context.org_id
    return None


def _raise_players_not_found(*, search_term: str | None = None) -> None:
    """Raise when a search returns no matching players."""
    message = "No players match the search criteria"
    if search_term:
        message = f"No players match '{search_term}'"
    raise AppException(
        code="PLAYERS_NOT_FOUND",
        message=message,
        status_code=404,
        details=[
            {
                "field": "search_query",
                "message": "No players match the provided search criteria",
            }
        ],
    )


async def get_authenticated_leaderboard(
    db: AsyncSession,
    user: User,
    *,
    search_query: str | None = None,
    full_name: str | None = None,
    phone: str | None = None,
    org_id: UUID | None = None,
) -> dict[str, Any]:
    """Return org-scoped leaderboard data for an authenticated user."""
    scoped_org_id = org_id if org_id is not None else await resolve_leaderboard_org_id(db, user)
    has_search = search_query is not None or full_name is not None

    if has_search:
        term = leaderboard_service.resolve_search_text(
            search_query=search_query,
            full_name=full_name,
        )
        items = await leaderboard_service._aggregate_player_stats(
            db,
            org_id=scoped_org_id,
            search_term=term,
            sort_metric=LeaderboardFilterMetric.SHOOTING_PERCENT,
        )
        if not items:
            _raise_players_not_found(search_term=term)
        result = leaderboard_service._build_list_response(
            items,
            message="Leaderboard search completed successfully",
            description=f"Players matching '{term}'",
        )
    else:
        items = await leaderboard_service._aggregate_player_stats(
            db,
            org_id=scoped_org_id,
            sort_metric=LeaderboardFilterMetric.SHOOTING_PERCENT,
        )
        result = leaderboard_service._build_list_response(
            items,
            message="Leaderboard loaded successfully",
            description="Top players ranked by shooting percentage",
        )

    result["phone"] = phone
    logger.info(
        "Loaded authenticated leaderboard for user %s (%s rows)",
        user.id,
        len(result["items"]),
    )
    return result


async def search_authenticated_leaderboard(
    db: AsyncSession,
    user: User,
    *,
    search_query: str | None = None,
    full_name: str | None = None,
    phone: str | None = None,
) -> dict[str, Any]:
    """Search players by name for an authenticated user."""
    term = leaderboard_service.resolve_search_text(
        search_query=search_query,
        full_name=full_name,
    )
    org_id = await resolve_leaderboard_org_id(db, user)
    items = await leaderboard_service._aggregate_player_stats(
        db,
        org_id=org_id,
        search_term=term,
        sort_metric=LeaderboardFilterMetric.SHOOTING_PERCENT,
    )
    if not items:
        _raise_players_not_found(search_term=term)

    result = leaderboard_service._build_list_response(
        items,
        message="Leaderboard search completed successfully",
        description=f"Players matching '{term}'",
    )
    result["phone"] = phone
    logger.info(
        "Leaderboard search for user %s returned %s players",
        user.id,
        len(items),
    )
    return result
