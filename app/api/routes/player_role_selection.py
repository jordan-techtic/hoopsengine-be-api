"""Player module ticket-path alias for role selection (HE-216)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.role_selection import (
    RoleSelectionCurrentResponse,
    RoleSelectionSubmitRequest,
    RoleSelectionSubmitResponse,
)
from app.services import role_selection as role_selection_service

player_alias_router = APIRouter(prefix="/player/role-selection", tags=["player-role-selection"])

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Missing, empty, undefined, or invalid role selection",
        examples={
            "role_required": {
                "code": "VALIDATION_ERROR",
                "message": "A role must be selected before continuing",
                "details": [
                    {
                        "field": "selected_role",
                        "message": "A role must be selected before continuing",
                    }
                ],
            },
            "role_invalid": {
                "code": "VALIDATION_ERROR",
                "message": "The selected role is not valid",
                "details": [
                    {
                        "field": "selected_role",
                        "message": "The selected role is not valid",
                    }
                ],
            },
            "role_undefined": {
                "code": "VALIDATION_ERROR",
                "message": "The selected role is not defined",
                "details": [
                    {
                        "field": "selected_role",
                        "message": "The selected role is not defined",
                    }
                ],
            },
        },
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=[{"field": "selected_role", "message": "Field required"}],
    ),
}

CONFLICT_ERROR_RESPONSES = {
    409: openapi_error(
        "Unchanged role resubmission",
        code="ROLE_SELECTION_UNCHANGED",
        message="Role selection has already been saved with this role",
        details=[
            {
                "field": "selected_role",
                "message": "Role selection has already been saved with this role",
            }
        ],
    ),
}

NOT_FOUND_ERROR_RESPONSE = {
    404: openapi_error(
        "Unknown role selection session token",
        code="ROLE_SELECTION_NOT_FOUND",
        message="Role selection session not found",
        details=[
            {
                "field": "session_token",
                "message": "Role selection session not found",
            }
        ],
    ),
}


def _map_invalid_role_to_400(exc: AppException) -> AppException:
    """Map disallowed roles to 400 for the player ticket path acceptance criteria."""
    if exc.code != "ROLE_NOT_ALLOWED":
        return exc
    return AppException(
        code="VALIDATION_ERROR",
        message="The selected role is not valid",
        status_code=400,
        details=[
            {
                "field": "selected_role",
                "message": "The selected role is not valid",
            }
        ],
    )


async def _submit_player_role_selection(
    db: AsyncSession,
    body: RoleSelectionSubmitRequest,
) -> dict[str, object]:
    """Submit role selection with player-path error mapping for invalid roles."""
    try:
        return await role_selection_service.submit_role_selection(
            db,
            selected_role=body.selected_role,
            session_token=body.session_token,
        )
    except AppException as exc:
        raise _map_invalid_role_to_400(exc) from exc


@player_alias_router.get(
    "",
    response_model=RoleSelectionCurrentResponse,
    operation_id="getPlayerRoleSelection",
    summary="Get current role selection (player path)",
    description=(
        "Ticket-path alias for **GET /api/v1/player/role-selection**.\n\n"
        "Return the saved role for an onboarding session identified by `session_token`.\n\n"
        "**Public endpoint** — no authentication required.\n\n"
        "Returns **404** when the session token is unknown."
    ),
    responses={
        **NOT_FOUND_ERROR_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_player_role_selection(
    session_token: UUID = Query(
        ...,
        description="Role selection session token returned from POST /player/role-selection",
        examples=["11111111-2222-3333-4444-555555555555"],
    ),
    db: AsyncSession = Depends(get_db),
) -> RoleSelectionCurrentResponse:
    """Retrieve the current role selection for a session token."""
    result = await role_selection_service.get_current_selection(db, session_token)
    return RoleSelectionCurrentResponse(**result)


@player_alias_router.post(
    "",
    response_model=RoleSelectionSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="submitPlayerRoleSelection",
    summary="Submit selected role (player path)",
    description=(
        "Ticket-path alias for **POST /api/v1/player/role-selection**.\n\n"
        "Save the user's role choice (Coach, Player, or Organiser) and return a session token "
        "for the registration step.\n\n"
        "**Public endpoint** — no authentication required.\n\n"
        "**Required body field:** `selected_role` (`coach`, `player`, or `organiser`).\n\n"
        "Optional `phone` is client metadata from the status bar and is **not persisted**.\n\n"
        "Optional `session_token` updates an existing selection; omit it on first submission.\n\n"
        "Returns **201** with `session_token`, `selected_role`, `role`, and `link`.\n\n"
        "Returns **400** when no role is selected or the role is invalid.\n\n"
        "Returns **409** when the same role is resubmitted unchanged."
    ),
    responses={
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def submit_player_role_selection(
    body: RoleSelectionSubmitRequest,
    db: AsyncSession = Depends(get_db),
) -> RoleSelectionSubmitResponse:
    """Save role selection from the player module Role Selection screen."""
    result = await _submit_player_role_selection(db, body)
    return RoleSelectionSubmitResponse(**result)
