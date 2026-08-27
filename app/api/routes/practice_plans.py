"""Coach practice plan CRUD endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error
from app.schemas.practice_plan import (
    PracticePlanCreateRequest,
    PracticePlanListResponse,
    PracticePlanResponse,
    PracticePlanUpdateRequest,
)
from app.services import practice_plan as practice_plan_service

router = APIRouter(prefix="/practice-plans", tags=["coach-practice-plans"])

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
        "User is not an authenticated verified coach",
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
        "Duplicate practice plan name for this coach",
        code="PRACTICE_PLAN_NAME_EXISTS",
        message="A practice plan with this name already exists",
        details=[{"field": "name", "message": "A practice plan with this name already exists"}],
    ),
}

NOT_FOUND_ERROR_RESPONSE = {
    404: openapi_error(
        "Practice plan not found or not owned by the authenticated coach",
        code="PRACTICE_PLAN_NOT_FOUND",
        message="Practice plan not found",
    ),
}


@router.post(
    "",
    response_model=PracticePlanResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createPracticePlan",
    summary="Create a practice plan",
    description=(
        "Create a new active practice plan for the authenticated coach.\n\n"
        "Required fields: `name`, `drills` (at least one drill with `id`, `name`, and `type`). "
        "Optional `phone` is client metadata and is not persisted.\n\n"
        "Returns **409** when an active plan with the same name already exists for the coach.\n\n"
        "Returns **400** when required business fields are empty after trimming.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSE,
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
async def create_practice_plan(
    body: PracticePlanCreateRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> PracticePlanResponse:
    result = await practice_plan_service.create_practice_plan(db, current_user, body)
    return PracticePlanResponse(**result)


@router.get(
    "",
    response_model=PracticePlanListResponse,
    operation_id="listPracticePlans",
    summary="List active practice plans",
    description=(
        "Return active practice plans owned by the authenticated coach.\n\n"
        "Each plan includes `name`, `drill_count`, `created_by_name`, and nested `drills`.\n\n"
        "Inactive or deleted plans are excluded. An empty `plans` array is a valid empty state.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
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
async def list_practice_plans(
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> PracticePlanListResponse:
    result = await practice_plan_service.list_active_practice_plans(db, current_user)
    return PracticePlanListResponse(**result)


@router.put(
    "/{plan_id}",
    response_model=PracticePlanResponse,
    operation_id="updatePracticePlan",
    summary="Update a practice plan",
    description=(
        "Update an existing practice plan owned by the authenticated coach.\n\n"
        "Provide `name` and/or `drills`. Optional `phone` is client metadata and is not persisted.\n\n"
        "Returns **404** when the plan does not exist or is not owned by the coach.\n\n"
        "Returns **409** when renaming to a duplicate active plan name.\n\n"
        "Returns **400** for invalid update payloads (empty name, empty drills, etc.).\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSE,
        **NOT_FOUND_ERROR_RESPONSE,
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
async def update_practice_plan(
    body: PracticePlanUpdateRequest,
    plan_id: UUID = PLAN_ID_PATH,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> PracticePlanResponse:
    result = await practice_plan_service.update_practice_plan(db, current_user, plan_id, body)
    return PracticePlanResponse(**result)


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deletePracticePlan",
    summary="Delete a practice plan",
    description=(
        "Delete (deactivate) a practice plan owned by the authenticated coach.\n\n"
        "Returns **204 No Content** on success. The plan will no longer appear in active listings.\n\n"
        "Returns **404** when the plan does not exist or is not owned by the coach.\n\n"
        "**Requires authenticated verified coach JWT**."
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
            "Practice plan tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Practice plan operations are temporarily unavailable",
        ),
    },
)
async def delete_practice_plan(
    plan_id: UUID = PLAN_ID_PATH,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await practice_plan_service.delete_practice_plan(db, current_user, plan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
