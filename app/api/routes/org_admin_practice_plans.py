"""Organization admin practice plan CRUD endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error
from app.schemas.org_admin_practice_plan import (
    OrgAdminPracticePlanCreateRequest,
    OrgAdminPracticePlanListResponse,
    OrgAdminPracticePlanResponse,
    OrgAdminPracticePlanUpdateRequest,
)
from app.services import org_admin_practice_plan as org_admin_practice_plan_service

router = APIRouter(prefix="/admin/practice-plans", tags=["org-admin-practice-plans"])

PLAN_ID_PATH = Path(
    ...,
    description="Practice plan UUID",
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
    400: openapi_error(
        "Invalid or missing practice plan fields",
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=[{"field": "name", "message": "Practice plan name is required"}],
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

CONFLICT_ERROR_RESPONSE = {
    409: openapi_error(
        "Duplicate practice plan name for this organization",
        code="PRACTICE_PLAN_NAME_EXISTS",
        message="A practice plan with this name already exists",
        details=[{"field": "name", "message": "A practice plan with this name already exists"}],
    ),
}

NOT_FOUND_ERROR_RESPONSES = {
    404: openapi_error(
        "Practice plan or organization profile not found",
        code="PRACTICE_PLAN_NOT_FOUND",
        message="Practice plan not found",
    ),
}


@router.get(
    "",
    response_model=OrgAdminPracticePlanListResponse,
    operation_id="listOrgAdminPracticePlans",
    summary="List organization practice plans",
    description=(
        "Return all active practice plans for the authenticated organization admin's organization.\n\n"
        "Each plan includes `id`, `name`, `title`, `description`, `drill_count`, `duration`, "
        "`category`, `created_by_name` (coach responsible), `organization`, and nested `drills` "
        "with `drill_name` and `drill_description`.\n\n"
        "An empty `plans` array is a valid empty-state response.\n\n"
        "Returns **404** when the admin account is not linked to an organization.\n\n"
        "**Requires organization admin JWT** (`Authorization: Bearer <access_token>`)."
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
            "Practice plan tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Practice plan operations are temporarily unavailable",
        ),
    },
)
async def list_org_practice_plans(
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminPracticePlanListResponse:
    """Return active practice plans for the organization admin Practice Plans screen."""
    payload = await org_admin_practice_plan_service.list_org_practice_plans(db, current_user)
    return OrgAdminPracticePlanListResponse(**payload)


@router.post(
    "",
    response_model=OrgAdminPracticePlanResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createOrgAdminPracticePlan",
    summary="Create an organization practice plan",
    description=(
        "Create a new active practice plan for the authenticated organization admin's organization.\n\n"
        "**Required body fields:** `name`, `drills` (at least one entry with `drill_name`). "
        "Optional `description` stores plan details. Optional `phone` is client metadata "
        "from the status bar and is not persisted.\n\n"
        "Each drill accepts `drill_name` and optional `drill_description`.\n\n"
        "Returns **201** on success. Returns **409** when an active plan with the same name "
        "already exists in the organization. Returns **400** when required fields are missing "
        "or invalid.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSE,
        **NOT_FOUND_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Practice plan tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Practice plan operations are temporarily unavailable",
        ),
    },
)
async def create_org_practice_plan(
    body: OrgAdminPracticePlanCreateRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminPracticePlanResponse:
    """Create a practice plan from the Organization Admin Practice Plans screen."""
    payload = await org_admin_practice_plan_service.create_org_practice_plan(
        db,
        current_user,
        body,
    )
    return OrgAdminPracticePlanResponse(**payload)


@router.put(
    "/{plan_id}",
    response_model=OrgAdminPracticePlanResponse,
    operation_id="updateOrgAdminPracticePlan",
    summary="Update an organization practice plan",
    description=(
        "Update an existing practice plan in the authenticated organization admin's organization.\n\n"
        "Provide `name`, `description`, and/or `drills`. Optional `phone` is client metadata "
        "and is not persisted.\n\n"
        "Returns **200** on success. Returns **404** when the plan does not exist in the "
        "organization. Returns **409** when renaming to a duplicate active plan name. "
        "Returns **400** for invalid update payloads.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSE,
        **NOT_FOUND_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Practice plan tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Practice plan operations are temporarily unavailable",
        ),
    },
)
async def update_org_practice_plan(
    body: OrgAdminPracticePlanUpdateRequest,
    plan_id: UUID = PLAN_ID_PATH,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminPracticePlanResponse:
    """Update a practice plan from the Organization Admin Practice Plans screen."""
    payload = await org_admin_practice_plan_service.update_org_practice_plan(
        db,
        current_user,
        plan_id,
        body,
    )
    return OrgAdminPracticePlanResponse(**payload)


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteOrgAdminPracticePlan",
    summary="Delete an organization practice plan",
    description=(
        "Delete (deactivate) a practice plan in the authenticated organization admin's organization.\n\n"
        "Returns **204 No Content** on success. The plan will no longer appear in active listings.\n\n"
        "Returns **404** when the plan does not exist in the organization.\n\n"
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
            "Practice plan tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Practice plan operations are temporarily unavailable",
        ),
    },
)
async def delete_org_practice_plan(
    plan_id: UUID = PLAN_ID_PATH,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Soft-delete a practice plan from the Organization Admin Practice Plans screen."""
    await org_admin_practice_plan_service.delete_org_practice_plan(db, current_user, plan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
