"""Team Details endpoints for the Organization Admin module."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org_admin, get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.team import (
    TeamCreateRequest,
    TeamDetailsResponse,
    TeamListResponse,
    TeamSearchResponse,
    TeamUpdateRequest,
)
from app.services import team as team_service

router = APIRouter(prefix="/teams", tags=["teams"])

TEAM_ID_PATH = Path(
    ...,
    description="Team UUID",
    examples=["11111111-2222-3333-4444-555555555555"],
)

AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing, invalid, expired, or revoked JWT",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
}

FORBIDDEN_ERROR_RESPONSE = {
    403: openapi_error(
        "Authenticated user is not an organization admin",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Invalid or missing Team Details fields",
        examples={
            "missing_name": {
                "code": "VALIDATION_ERROR",
                "message": "Team name is required",
                "details": [{"field": "name", "message": "Team name is required"}],
            },
            "empty_email": {
                "code": "VALIDATION_ERROR",
                "message": "Email is required",
                "details": [{"field": "email", "message": "Email is required"}],
            },
            "invalid_email": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid email address",
                "details": [{"field": "email", "message": "Enter a valid email address"}],
            },
            "empty_update_body": {
                "code": "VALIDATION_ERROR",
                "message": "At least one field must be provided to update a team",
                "details": [
                    {
                        "field": "name",
                        "message": "Provide at least one updatable field",
                    }
                ],
            },
            "empty_search_query": {
                "code": "VALIDATION_ERROR",
                "message": "Search query is required",
                "details": [{"field": "query", "message": "Search query is required"}],
            },
            "missing_age_group": {
                "code": "VALIDATION_ERROR",
                "message": "Age group is required",
                "details": [{"field": "age_group", "message": "Age group is required"}],
            },
            "missing_coaches": {
                "code": "VALIDATION_ERROR",
                "message": "At least one coach is required",
                "details": [{"field": "coaches", "message": "At least one coach is required"}],
            },
            "missing_players": {
                "code": "VALIDATION_ERROR",
                "message": "At least one player is required",
                "details": [{"field": "players", "message": "At least one player is required"}],
            },
        },
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

CONFLICT_ERROR_RESPONSES = {
    409: openapi_error_examples(
        "Duplicate team name or email",
        examples={
            "duplicate_team_name": {
                "code": "TEAM_NAME_EXISTS",
                "message": "A team with this name already exists",
                "details": [{"field": "name", "message": "A team with this name already exists"}],
            },
            "duplicate_email": {
                "code": "EMAIL_ALREADY_IN_USE",
                "message": "This email is already in use by another account",
                "details": [
                    {
                        "field": "email",
                        "message": "This email is already in use by another account",
                    }
                ],
            },
            "team_has_players": {
                "code": "TEAM_HAS_PLAYERS",
                "message": "Remove players from this team before deleting it",
                "details": [
                    {
                        "field": "team_id",
                        "message": "Remove players from this team before deleting it",
                    }
                ],
            },
        },
    ),
}

NOT_FOUND_ERROR_RESPONSE = {
    404: openapi_error(
        "Team or organization profile not found",
        code="TEAM_NOT_FOUND",
        message="Team not found",
        details=[{"field": "team_id", "message": "Team not found"}],
    ),
}


@router.get(
    "/search",
    response_model=TeamSearchResponse,
    operation_id="searchTeams",
    summary="Search teams by name",
    description=(
        "Search organization teams by display name for the **Team Listing** screen "
        "(HE-334).\n\n"
        "Requires non-empty `query` parameter. Returns paginated matching teams "
        "with coach and player display names.\n\n"
        "Returns **400** when `query` is empty.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **FORBIDDEN_ERROR_RESPONSE,
        **VALIDATION_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Team tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Team operations are temporarily unavailable",
        ),
    },
)
async def search_teams(
    query: str = Query(
        ...,
        description="Team name search term",
        examples=["Varsity"],
    ),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of teams per page"),
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> TeamSearchResponse:
    """Search teams by name for the Team Listing screen."""
    payload = await team_service.search_teams(
        db,
        current_user,
        query=query,
        page=page,
        page_size=page_size,
    )
    return TeamSearchResponse(**payload)


@router.get(
    "",
    response_model=TeamListResponse,
    operation_id="listTeams",
    summary="List organization teams",
    description=(
        "Return a paginated list of teams for the Organization Admin **Team Listing** "
        "screen (HE-334).\n\n"
        "Each item includes team name, age group, primary coach email, roster names, "
        "and status.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **FORBIDDEN_ERROR_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Team tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Team operations are temporarily unavailable",
        ),
    },
)
async def list_teams(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of teams per page"),
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> TeamListResponse:
    """List teams for the Team Listing screen."""
    payload = await team_service.list_teams(
        db,
        current_user,
        page=page,
        page_size=page_size,
    )
    return TeamListResponse(**payload)


@router.get(
    "/{team_id}",
    response_model=TeamDetailsResponse,
    operation_id="getTeamDetails",
    summary="Retrieve team details",
    description=(
        "Return comprehensive team details for the Organization Admin **Team Details** "
        "screen (HE-337).\n\n"
        "Includes team roster fields (`name`, `season`, `home_ground`, `coaches`, "
        "`players`, `founded`, `age_group`, `training_schedule`) and primary coach "
        "contact fields (`email`, `phone`, `phone_number`, `role`, `roles`).\n\n"
        "**Any authenticated user** in the organization may view team details.\n\n"
        "Returns **404** when the team does not exist in the user's organization."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Team tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Team operations are temporarily unavailable",
        ),
    },
)
async def get_team_details(
    team_id: UUID = TEAM_ID_PATH,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamDetailsResponse:
    """Retrieve team details for the Team Details screen."""
    payload = await team_service.get_team(db, current_user, team_id)
    return TeamDetailsResponse(**payload)


@router.post(
    "",
    response_model=TeamDetailsResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createTeamDetails",
    summary="Create a team",
    description=(
        "Create a new team for Organization Admin team management.\n\n"
        "Supports the **Team Listing** flow (HE-334) with required fields `name`, "
        "`age_group`, `coaches`, and `players` (each with a `name` property), plus "
        "optional Figma `phone` metadata.\n\n"
        "Also supports the **Team Details** flow (HE-337) when `email` is provided "
        "for the primary coach.\n\n"
        "Returns **201** on success. Returns **400** when required fields are missing "
        "or invalid. Returns **409** when the team name or email already exists.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **FORBIDDEN_ERROR_RESPONSE,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Team tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Team operations are temporarily unavailable",
        ),
    },
)
async def create_team_details(
    body: TeamCreateRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> TeamDetailsResponse:
    """Create a team from the Team Details screen."""
    payload = await team_service.create_team(db, current_user, body)
    return TeamDetailsResponse(**payload)


@router.put(
    "/{team_id}",
    response_model=TeamDetailsResponse,
    operation_id="updateTeamDetails",
    summary="Update team details",
    description=(
        "Update team and primary coach details from the Organization Admin **Team "
        "Details** screen (HE-337).\n\n"
        "Accepts Figma fields `email`, `phone`, and optional team attributes "
        "(`name`, `season`, `home_ground`, `age_group`, `training_schedule`, `founded`, "
        "`role`).\n\n"
        "Returns **200** with a success message on update. Returns **404** when the "
        "team is not found. Returns **409** when the email is already registered.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **FORBIDDEN_ERROR_RESPONSE,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Team tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Team operations are temporarily unavailable",
        ),
    },
)
async def update_team_details(
    body: TeamUpdateRequest,
    team_id: UUID = TEAM_ID_PATH,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> TeamDetailsResponse:
    """Update team details from the Team Details screen."""
    payload = await team_service.update_team(db, current_user, team_id, body)
    return TeamDetailsResponse(**payload)


@router.delete(
    "/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteTeamDetails",
    summary="Delete a team",
    description=(
        "Delete a team from the Organization Admin **Team Details** flow (HE-337).\n\n"
        "Returns **204 No Content** on success. Coach assignments are cleared "
        "automatically.\n\n"
        "Returns **404** when the team does not exist. Returns **409** when players "
        "are still assigned to the team.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **FORBIDDEN_ERROR_RESPONSE,
        **NOT_FOUND_ERROR_RESPONSE,
        **CONFLICT_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Team tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Team operations are temporarily unavailable",
        ),
    },
)
async def delete_team_details(
    team_id: UUID = TEAM_ID_PATH,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a team from the Team Details screen."""
    await team_service.delete_team(db, current_user, team_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
