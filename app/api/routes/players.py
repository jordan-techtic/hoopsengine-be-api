"""Coach and organization admin player detail endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach, get_current_user
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.org_admin_player import (
    OrgAdminPlayerDetailResponse,
    OrgAdminPlayerListResponse,
)
from app.schemas.player import (
    PlayerCreateRequest,
    PlayerCreateResponse,
    PlayerDeleteResponse,
    PlayerDetailResponse,
    PlayerListResponse,
    PlayerSearchResponse,
    PlayerUpdateRequest,
)
from app.services import org_admin_player as org_admin_player_service
from app.services import player as player_service

router = APIRouter(prefix="/players", tags=["players"])

PLAYER_ID_PATH = Path(
    ...,
    description="Player UUID",
    examples=["11111111-2222-3333-4444-555555555555"],
)

AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing, invalid, expired, or revoked JWT",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
    403: openapi_error(
        "User is not an authenticated verified coach",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Invalid or empty player fields",
        examples={
            "invalid_email": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid email address",
                "details": [{"field": "email", "message": "Enter a valid email address"}],
            },
            "invalid_phone": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid phone number",
                "details": [{"field": "phone_number", "message": "Enter a valid phone number"}],
            },
            "empty_field": {
                "code": "VALIDATION_ERROR",
                "message": "First name cannot be empty",
                "details": [{"field": "first_name", "message": "First name cannot be empty"}],
            },
        },
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

CONFLICT_ERROR_RESPONSE = {
    409: openapi_error(
        "Email already registered to another player",
        code="EMAIL_ALREADY_IN_USE",
        message="This email is already registered to another player",
        details=[
            {
                "field": "email",
                "message": "This email is already registered to another player",
            }
        ],
    ),
}

NOT_FOUND_ERROR_RESPONSE = {
    404: openapi_error(
        "Player not found or not in the coach organization",
        code="PLAYER_NOT_FOUND",
        message="Player not found",
        details=[{"field": "player_id", "message": "Player not found"}],
    ),
}

SEARCH_VALIDATION_ERROR_RESPONSE = {
    400: openapi_error(
        "Empty search query",
        code="VALIDATION_ERROR",
        message="Search query is required",
        details=[
            {
                "field": "search_query",
                "message": "Provide search_query or full_name to search players",
            }
        ],
    ),
}


def _authorize_coach_or_org_admin(current_user: User) -> User:
    """Allow verified coaches or organization admins to manage roster players."""
    if current_user.role == UserRole.ORG_ADMIN.value:
        return current_user
    if current_user.role == UserRole.COACH.value:
        if current_user.email_confirmed_at is None:
            raise AppException(
                code="FORBIDDEN",
                message="Email verification is required to access this resource",
                status_code=403,
            )
        return current_user
    raise AppException(
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
        status_code=403,
    )


async def get_coach_or_org_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency that permits coach or organization admin access."""
    return _authorize_coach_or_org_admin(current_user)


@router.post(
    "",
    response_model=PlayerCreateResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createPlayer",
    summary="Add a new player",
    description=(
        "Create a new player record for the authenticated coach's organization.\n\n"
        "**Requires authenticated verified coach JWT** (`Authorization: Bearer <access_token>`).\n\n"
        "Accepts Figma fields `first_name`, `last_name`, `email`, and optional client "
        "metadata `phone` (not persisted).\n\n"
        "Also requires `phone_number`, `gender`, `date_of_birth` (YYYY-MM-DD or MM/DD/YYYY), "
        "and `team_selection` (team name within the organization).\n\n"
        "Returns **201** when the player is created successfully.\n\n"
        "Returns **400** when required fields are empty or email, phone, date, or team is invalid.\n\n"
        "Returns **409** when the email is already registered to another player in the organization."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSE,
        503: openapi_error(
            "Players table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Player operations are temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def create_player(
    body: PlayerCreateRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> PlayerCreateResponse:
    """Create a new player for the Add Player screen."""
    result = await player_service.create_player(db, current_user, body)
    return PlayerCreateResponse(**result)


@router.get(
    "",
    response_model=PlayerListResponse | OrgAdminPlayerListResponse,
    operation_id="listPlayers",
    summary="List organization players",
    description=(
        "Return active players associated with the authenticated user's organization.\n\n"
        "**Requires authenticated verified coach or organization admin JWT** "
        "(`Authorization: Bearer <access_token>`).\n\n"
        "Coaches receive the **My Players** list shape. Organization admins receive "
        "the **Player Management** list with the same player summary cards "
        "(`id`, `name`, `player_code`, `code`, `team_name`).\n\n"
        "Only **active** roster players are included.\n\n"
        "Returns **200** with an empty `players` array when no active roster players exist."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        403: openapi_error(
            "User is not an authenticated verified coach or organization admin",
            code="FORBIDDEN",
            message="You do not have permission to access this resource",
        ),
        503: openapi_error(
            "Players table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Player operations are temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def list_players(
    current_user: User = Depends(get_coach_or_org_admin),
    db: AsyncSession = Depends(get_db),
) -> PlayerListResponse | OrgAdminPlayerListResponse:
    """List active players for the coach My Players or org-admin Player Management screen."""
    if current_user.role == UserRole.ORG_ADMIN.value:
        result = await org_admin_player_service.list_players(db, current_user)
        return OrgAdminPlayerListResponse(**result)
    result = await player_service.list_players(db, current_user)
    return PlayerListResponse(**result)


@router.get(
    "/search",
    response_model=PlayerSearchResponse,
    operation_id="searchPlayers",
    summary="Search coach players",
    description=(
        "Search active players by name or player code within the coach's organization.\n\n"
        "**Requires authenticated verified coach JWT**.\n\n"
        "Provide `search_query` and/or Figma `full_name`. Optional `phone` is client "
        "metadata from the status bar and is not persisted.\n\n"
        "Matches against first name, last name, full name, or `player_code`.\n\n"
        "Returns **400** when both `search_query` and `full_name` are empty.\n\n"
        "Returns **200** with an empty `players` array when no matches are found."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **SEARCH_VALIDATION_ERROR_RESPONSE,
        503: openapi_error(
            "Players table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Player operations are temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def search_players(
    search_query: str | None = Query(
        default=None,
        description="Search text matched against player name or player code",
        examples=["Jane"],
    ),
    full_name: str | None = Query(
        default=None,
        description="Figma Player Name search input (`full_name`)",
        examples=["Jane Doe"],
    ),
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    ),
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> PlayerSearchResponse:
    """Search players for the My Players screen."""
    result = await player_service.search_players(
        db,
        current_user,
        search_query=search_query,
        full_name=full_name,
        phone=phone,
    )
    return PlayerSearchResponse(**result)


@router.get(
    "/{player_id}",
    response_model=PlayerDetailResponse | OrgAdminPlayerDetailResponse,
    operation_id="getPlayerDetail",
    summary="Get player details",
    description=(
        "Return player profile, statistics, and contact information for the "
        "**Player Details** screen.\n\n"
        "**Requires authenticated verified coach or organization admin JWT**.\n\n"
        "The player must belong to the caller's organization and be active.\n\n"
        "Coaches receive flat statistic fields (`games_played`, `goals`, etc.). "
        "Organization admins receive `first_name`, `last_name`, and a nested `stats` "
        "object with `games_played`, `goals`, `assists`, and `yellow_cards`.\n\n"
        "Accepts Figma fields `email` and `phone_number` in responses. Optional `phone` "
        "is client metadata and is not persisted.\n\n"
        "Returns **404** when the player does not exist, is inactive, or is outside "
        "the caller's organization."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        403: openapi_error(
            "User is not an authenticated verified coach or organization admin",
            code="FORBIDDEN",
            message="You do not have permission to access this resource",
        ),
        **NOT_FOUND_ERROR_RESPONSE,
        503: openapi_error(
            "Players table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Player operations are temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_player_detail(
    player_id: UUID = PLAYER_ID_PATH,
    current_user: User = Depends(get_coach_or_org_admin),
    db: AsyncSession = Depends(get_db),
) -> PlayerDetailResponse | OrgAdminPlayerDetailResponse:
    """Retrieve player details by id for an authenticated coach or organization admin."""
    if current_user.role == UserRole.ORG_ADMIN.value:
        result = await org_admin_player_service.get_player_detail(db, current_user, player_id)
        return OrgAdminPlayerDetailResponse(**result)
    result = await player_service.get_player_detail_for_coach(db, current_user, player_id)
    return PlayerDetailResponse(**result)


@router.put(
    "/{player_id}",
    response_model=PlayerDetailResponse | OrgAdminPlayerDetailResponse,
    operation_id="updatePlayerDetail",
    summary="Update player details",
    description=(
        "Update player contact and profile fields for an authenticated coach or "
        "organization admin.\n\n"
        "**Requires authenticated verified coach or organization admin JWT** "
        "(`Authorization: Bearer <access_token>`).\n\n"
        "Accepts Figma fields `email` (Coach_Email) and `phone_number` (stored as "
        "`players.phone`). Optional `phone` is client metadata and is not persisted.\n\n"
        "Also accepts `first_name`, `last_name`, and `position`.\n\n"
        "Returns **400** for invalid email or phone format, or empty required text fields.\n\n"
        "Returns **409** when the email is already registered to another player in the organization.\n\n"
        "Returns **404** when the player is not found in the caller's organization.\n\n"
        "Organization admins receive the nested `stats` response shape on success."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        403: openapi_error(
            "User is not an authenticated verified coach or organization admin",
            code="FORBIDDEN",
            message="You do not have permission to access this resource",
        ),
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSE,
        **NOT_FOUND_ERROR_RESPONSE,
        503: openapi_error(
            "Players table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Player operations are temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def update_player_detail(
    body: PlayerUpdateRequest,
    player_id: UUID = PLAYER_ID_PATH,
    current_user: User = Depends(get_coach_or_org_admin),
    db: AsyncSession = Depends(get_db),
) -> PlayerDetailResponse | OrgAdminPlayerDetailResponse:
    """Update player details for a coach-owned or org-admin-managed roster player."""
    if current_user.role == UserRole.ORG_ADMIN.value:
        result = await org_admin_player_service.update_player(db, current_user, player_id, body)
        return OrgAdminPlayerDetailResponse(**result)
    result = await player_service.update_player(db, current_user, player_id, body)
    return PlayerDetailResponse(**result)


@router.delete(
    "/{player_id}",
    response_model=PlayerDeleteResponse,
    status_code=status.HTTP_200_OK,
    operation_id="deletePlayerDetail",
    summary="Remove player from roster",
    description=(
        "Soft-delete a player by setting `active=false` when supported.\n\n"
        "**Requires authenticated verified coach JWT**.\n\n"
        "Returns **404** when the player is not found in the coach's organization."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        503: openapi_error(
            "Players table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Player operations are temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def delete_player_detail(
    player_id: UUID = PLAYER_ID_PATH,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> PlayerDeleteResponse:
    """Remove a player from the coach roster."""
    result = await player_service.delete_player(db, current_user, player_id)
    return PlayerDeleteResponse(**result)
