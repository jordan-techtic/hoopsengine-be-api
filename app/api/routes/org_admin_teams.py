"""Organization admin team CRUD endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.org_admin_team import (
    OrgAdminTeamCreateRequest,
    OrgAdminTeamResponse,
    OrgAdminTeamUpdateRequest,
)
from app.services import org_admin_team as org_admin_team_service

router = APIRouter(prefix="/admin/teams", tags=["org-admin-teams"])

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
    403: openapi_error(
        "Authenticated user is not an organization admin",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Invalid or missing team fields",
        examples={
            "empty_team_name": {
                "code": "VALIDATION_ERROR",
                "message": "Team name is required",
                "details": [{"field": "team_name", "message": "Team name is required"}],
            },
            "empty_body": {
                "code": "VALIDATION_ERROR",
                "message": "At least one field must be provided to update a team",
                "details": [
                    {
                        "field": "full_name",
                        "message": (
                            "Provide full_name, description, team_name, team_code, "
                            "team_description, age_group, and/or coaches"
                        ),
                    }
                ],
            },
            "coach_not_found": {
                "code": "COACH_NOT_FOUND",
                "message": "One or more assigned coaches were not found",
                "details": [
                    {
                        "field": "coaches[0].id",
                        "message": "Coach was not found in this organization",
                    }
                ],
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
        "Duplicate team name/code or team cannot be deleted while players remain",
        examples={
            "duplicate_team_name": {
                "code": "TEAM_NAME_EXISTS",
                "message": "A team with this name already exists",
                "details": [
                    {"field": "team_name", "message": "A team with this name already exists"}
                ],
            },
            "duplicate_team_code": {
                "code": "TEAM_CODE_EXISTS",
                "message": "A team with this code already exists",
                "details": [
                    {"field": "team_code", "message": "A team with this code already exists"}
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

NOT_FOUND_ERROR_RESPONSES = {
    404: openapi_error(
        "Team or organization profile not found",
        code="TEAM_NOT_FOUND",
        message="Team not found",
    ),
}


@router.post(
    "",
    response_model=OrgAdminTeamResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createOrgAdminTeam",
    summary="Create an organization team",
    description=(
        "Create a new team for the authenticated organization admin's organization.\n\n"
        "**Required body fields:** `team_name`, `team_code`. Optional `team_description`, "
        "`age_group`, and `coaches` (each with `id` and `name`). Optional `full_name` and "
        "`phone` are client metadata from the Create Team form and are not persisted.\n\n"
        "Returns **201** on success. Returns **409** when the team code already exists. "
        "Returns **400** when required fields are missing or invalid.\n\n"
        "**Requires organization admin JWT** (`Authorization: Bearer <access_token>`)."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSES,
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
async def create_org_team(
    body: OrgAdminTeamCreateRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminTeamResponse:
    """Create a team from the Organization Admin Create Team screen."""
    payload = await org_admin_team_service.create_org_team(db, current_user, body)
    return OrgAdminTeamResponse(**payload)


@router.get(
    "/{team_id}",
    response_model=OrgAdminTeamResponse,
    operation_id="getOrgAdminTeamForEdit",
    summary="Retrieve team details for editing",
    description=(
        "Return team details for the Organization Admin **Edit Team** screen (HE-372).\n\n"
        "Includes Figma fields `full_name` (as `name` and `full_name`), `description`, "
        "assigned `coaches` (each with `id` and `coach_id`), `organization`, and legacy "
        "`team_name`, `team_code`, and `team_description` fields.\n\n"
        "Returns **404** when the team does not exist in the organization.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSES,
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
async def get_org_team(
    team_id: UUID = TEAM_ID_PATH,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminTeamResponse:
    """Return one team for the Organization Admin Edit Team screen."""
    payload = await org_admin_team_service.get_org_team(db, current_user, team_id)
    return OrgAdminTeamResponse(**payload)


@router.put(
    "/{team_id}",
    response_model=OrgAdminTeamResponse,
    operation_id="updateOrgAdminTeamForEdit",
    summary="Update team details",
    description=(
        "Update an existing team from the Organization Admin **Edit Team** screen "
        "(HE-372).\n\n"
        "Accepts Figma fields `full_name` (Team Name), `description`, and `phone` "
        "(metadata only). Coach assignments accept `coaches[].coach_id` or `coaches[].id`.\n\n"
        "Legacy fields `team_name`, `team_code`, `team_description`, and `age_group` "
        "remain supported.\n\n"
        "Returns **200** on success. Returns **404** when the team does not exist. "
        "Returns **409** when renaming to a duplicate team name or team code.\n\n"
        "Returns **400** when the team name is empty or coach assignments are invalid.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSES,
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
async def update_org_team(
    body: OrgAdminTeamUpdateRequest,
    team_id: UUID = TEAM_ID_PATH,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminTeamResponse:
    """Update a team from the Organization Admin Edit Team screen."""
    payload = await org_admin_team_service.update_org_team(db, current_user, team_id, body)
    return OrgAdminTeamResponse(**payload)


@router.delete(
    "/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteOrgAdminTeam",
    summary="Delete an organization team",
    description=(
        "Delete a team from the authenticated organization admin's organization.\n\n"
        "Returns **204 No Content** on success. Coach assignments are cleared automatically.\n\n"
        "Returns **404** when the team does not exist. Returns **409** when players are "
        "still assigned to the team.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSES,
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
async def delete_org_team(
    team_id: UUID = TEAM_ID_PATH,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a team from the Organization Admin module."""
    await org_admin_team_service.delete_org_team(db, current_user, team_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
