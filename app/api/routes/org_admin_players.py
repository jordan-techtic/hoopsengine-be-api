"""Organization admin player edit and removal endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.org_admin_player import (
    OrgAdminPlayerDetailResponse,
    OrgAdminPlayerRemovalDetailResponse,
    OrgAdminPlayerRemovalRequest,
    OrgAdminPlayerRemovalResponse,
)
from app.schemas.player import PlayerUpdateRequest
from app.schemas.player_removal import REMOVAL_CONFIRMATION_MESSAGE
from app.services import org_admin_player as org_admin_player_service

router = APIRouter(prefix="/admin/players", tags=["org-admin-players"])

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
        "Authenticated user is not an organization admin",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
}

EDIT_VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Missing or invalid Edit Player fields",
        examples={
            "empty_full_name": {
                "code": "VALIDATION_ERROR",
                "message": "Full name is required",
                "details": [{"field": "full_name", "message": "Full name is required"}],
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
            "invalid_phone": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid phone number",
                "details": [{"field": "phone_number", "message": "Enter a valid phone number"}],
            },
            "invalid_team_assignment": {
                "code": "VALIDATION_ERROR",
                "message": "Selected team was not found in your organization",
                "details": [
                    {
                        "field": "team_assignment",
                        "message": "Selected team was not found in your organization",
                    }
                ],
            },
            "empty_body": {
                "code": "VALIDATION_ERROR",
                "message": "At least one player field must be provided",
                "details": [
                    {
                        "field": "body",
                        "message": "At least one player field must be provided",
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

REMOVAL_VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Missing or invalid removal confirmation fields",
        examples={
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
            "invalid_phone": {
                "code": "VALIDATION_ERROR",
                "message": "Phone number must contain 10 to 15 digits",
                "details": [
                    {"field": "phone", "message": "Phone number must contain 10 to 15 digits"}
                ],
            },
            "empty_full_name": {
                "code": "VALIDATION_ERROR",
                "message": "Full name is required",
                "details": [{"field": "full_name", "message": "Full name is required"}],
            },
        },
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

NOT_FOUND_ERROR_RESPONSE = {
    404: openapi_error(
        "Player not found in the organization",
        code="PLAYER_NOT_FOUND",
        message="Player not found",
        details=[{"field": "player_id", "message": "Player not found"}],
    ),
}

EDIT_CONFLICT_ERROR_RESPONSE = {
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

REMOVAL_CONFLICT_ERROR_RESPONSES = {
    409: openapi_error_examples(
        "Submitted credentials do not match the player or email belongs to another player",
        examples={
            "email_already_registered": {
                "code": "EMAIL_ALREADY_IN_USE",
                "message": "This email is already registered to another player",
                "details": [
                    {
                        "field": "email",
                        "message": "This email is already registered to another player",
                    }
                ],
            },
            "credentials_mismatch": {
                "code": "PLAYER_NOT_FOUND",
                "message": "No matching player was found for the provided details",
                "details": [
                    {
                        "field": "email",
                        "message": "No matching player was found for the provided details",
                    }
                ],
            },
        },
    ),
}


@router.get(
    "/{player_id}",
    response_model=OrgAdminPlayerDetailResponse,
    operation_id="getOrgAdminPlayerForEdit",
    summary="Retrieve player details for editing",
    description=(
        "Return player profile details for the Organization Admin **Edit Player** screen "
        "(HE-378).\n\n"
        "**Requires organization admin JWT** (`Authorization: Bearer <access_token>`).\n\n"
        "Includes Figma fields `full_name` (as `name` and `full_name`), `email`, `phone`, "
        "`phone_number`, and `team_assignment` (team display name).\n\n"
        "Also returns aggregated `stats` for the player detail cards.\n\n"
        "Returns **404** when the player does not exist, is inactive, or is outside "
        "the admin's organization."
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
async def get_org_admin_player_for_edit(
    player_id: UUID = PLAYER_ID_PATH,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminPlayerDetailResponse:
    """Retrieve player details for the Edit Player screen."""
    result = await org_admin_player_service.get_player_detail(db, current_user, player_id)
    return OrgAdminPlayerDetailResponse(**result)


@router.put(
    "/{player_id}",
    response_model=OrgAdminPlayerDetailResponse,
    operation_id="updateOrgAdminPlayer",
    summary="Update player details",
    description=(
        "Update a player record from the Organization Admin **Edit Player** screen "
        "(HE-378).\n\n"
        "Accepts Figma fields `full_name`, `email`, `phone`, and `team_assignment`. "
        "Optional legacy fields `first_name`, `last_name`, `phone_number`, and `name` "
        "are also supported.\n\n"
        "Returns **200** with updated player details on success.\n\n"
        "Returns **400** when required fields are empty, email format is invalid, or "
        "team assignment is not found.\n\n"
        "Returns **404** when the player is not in the admin's organization.\n\n"
        "Returns **409** when the email is already registered to another player.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **EDIT_VALIDATION_ERROR_RESPONSES,
        **EDIT_CONFLICT_ERROR_RESPONSE,
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
async def update_org_admin_player(
    body: PlayerUpdateRequest,
    player_id: UUID = PLAYER_ID_PATH,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminPlayerDetailResponse:
    """Update player details from the Edit Player form."""
    result = await org_admin_player_service.update_player(db, current_user, player_id, body)
    return OrgAdminPlayerDetailResponse(**result)


@router.get(
    "/{player_id}/removal",
    response_model=OrgAdminPlayerRemovalDetailResponse,
    operation_id="getOrgAdminPlayerRemovalDetail",
    summary="Get player details for removal confirmation",
    description=(
        "Return player profile details and the permanent deletion confirmation message "
        "for the Organization Admin **Remove Player** screen.\n\n"
        "**Requires organization admin JWT** (`Authorization: Bearer <access_token>`).\n\n"
        "Includes Figma fields `full_name` (as `name` and `full_name`), `email`, and `phone` "
        "(`phone_number` mirrors stored contact phone).\n\n"
        "Also returns `team`, `organization`, and `confirmation_message`:\n\n"
        f'"{REMOVAL_CONFIRMATION_MESSAGE}"\n\n'
        "Returns **404** when the player does not exist, is inactive, or is outside "
        "the admin's organization."
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
async def get_player_removal_detail(
    player_id: UUID = PLAYER_ID_PATH,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminPlayerRemovalDetailResponse:
    """Retrieve player details for the Remove Player confirmation modal."""
    result = await org_admin_player_service.get_player_removal_detail(db, current_user, player_id)
    return OrgAdminPlayerRemovalDetailResponse(**result)


@router.delete(
    "/{player_id}",
    response_model=OrgAdminPlayerRemovalResponse,
    status_code=status.HTTP_200_OK,
    operation_id="removeOrgAdminPlayer",
    summary="Remove player from organization",
    description=(
        "Remove an active player from the organization after confirming identity with "
        "`full_name`, `email`, and `phone`.\n\n"
        "**Requires organization admin JWT**.\n\n"
        "Returns **200** with `message` **Player removed successfully** when removal completes.\n\n"
        "Returns **400** when required fields are empty or email/phone formats are invalid.\n\n"
        "Returns **404** when the player id does not exist in the admin's organization.\n\n"
        "Returns **409** when the email is registered to another player or the submitted "
        "credentials do not match the target player record."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **REMOVAL_VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        **REMOVAL_CONFLICT_ERROR_RESPONSES,
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
async def remove_player(
    body: OrgAdminPlayerRemovalRequest,
    player_id: UUID = PLAYER_ID_PATH,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminPlayerRemovalResponse:
    """Remove a player from the organization after confirmation."""
    result = await org_admin_player_service.remove_player_by_id(
        db,
        current_user,
        player_id,
        full_name=body.full_name,
        email=body.email,
        phone=body.phone,
    )
    return OrgAdminPlayerRemovalResponse(**result)
