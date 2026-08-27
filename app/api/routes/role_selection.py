"""Public role selection endpoints for onboarding."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.role_selection import (
    RoleCatalogResponse,
    RoleSelectionCurrentResponse,
    RoleSelectionSubmitRequest,
    RoleSelectionSubmitResponse,
)
from app.services import role_selection as role_selection_service

router = APIRouter(prefix="/role-selection", tags=["role-selection"])

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Missing or empty role selection, or undefined role such as Referee",
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
    409: openapi_error_examples(
        "Role not offered on this screen or unchanged resubmission",
        examples={
            "role_not_allowed": {
                "code": "ROLE_NOT_ALLOWED",
                "message": "The selected role is not available for registration",
                "details": [
                    {
                        "field": "selected_role",
                        "message": "The selected role is not available for registration",
                    }
                ],
            },
            "role_unchanged": {
                "code": "ROLE_SELECTION_UNCHANGED",
                "message": "Role selection has already been saved with this role",
                "details": [
                    {
                        "field": "selected_role",
                        "message": "Role selection has already been saved with this role",
                    }
                ],
            },
        },
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


@router.get(
    "/roles",
    response_model=RoleCatalogResponse,
    operation_id="listRoleSelectionOptions",
    summary="List selectable roles",
    description=(
        "Return the Coach, Player, and Organiser options for the **Select Your Role** screen.\n\n"
        "**Public endpoint** — no authentication required.\n\n"
        "Each role includes `value`, `label`, and `description` for the role cards. "
        "The response also includes mobile envelope fields (`success`, `message`, `status`, "
        "`title`, `description`, `link`, `error`)."
    ),
    responses={
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def list_role_options() -> RoleCatalogResponse:
    """Return the static role catalog for the Role Selection screen."""
    result = role_selection_service.build_roles_catalog_response()
    return RoleCatalogResponse(**result)


@router.get(
    "",
    response_model=RoleSelectionCurrentResponse,
    operation_id="getCurrentRoleSelection",
    summary="Get current role selection",
    description=(
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
async def get_current_role_selection(
    session_token: UUID = Query(
        ...,
        description="Role selection session token returned from POST /role-selection",
        examples=["11111111-2222-3333-4444-555555555555"],
    ),
    db: AsyncSession = Depends(get_db),
) -> RoleSelectionCurrentResponse:
    """Retrieve the current role selection for a session token."""
    result = await role_selection_service.get_current_selection(db, session_token)
    return RoleSelectionCurrentResponse(**result)


@router.post(
    "",
    response_model=RoleSelectionSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="submitRoleSelection",
    summary="Submit selected role",
    description=(
        "Save the user's role choice (Coach, Player, or Organiser) and return a session token "
        "for the registration step.\n\n"
        "**Public endpoint** — no authentication required.\n\n"
        "**Required body field:** `selected_role`.\n\n"
        "Optional `phone` is client metadata from the status bar and is **not persisted**.\n\n"
        "Optional `session_token` updates an existing selection; omit it on first submission.\n\n"
        "Returns **201** with `session_token`, `selected_role`, `role`, and `link` pointing to registration.\n\n"
        "Returns **400** when no role is selected or the role is undefined (e.g. Referee).\n\n"
        "Returns **409** when the role is not offered on this screen or unchanged on resubmit."
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
async def submit_role_selection(
    body: RoleSelectionSubmitRequest,
    db: AsyncSession = Depends(get_db),
) -> RoleSelectionSubmitResponse:
    """Save role selection and return the next-step registration link."""
    result = await role_selection_service.submit_role_selection(
        db,
        selected_role=body.selected_role,
        session_token=body.session_token,
    )
    return RoleSelectionSubmitResponse(**result)
