"""Coach Edit Practice Plan endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach
from app.core.database import get_db
from app.models.user import User
from app.schemas.coach_practice_plan import (
    CoachPracticePlanCreateRequest,
    CoachPracticePlanResponse,
    CoachPracticePlanUpdateRequest,
)
from app.schemas.errors import openapi_error
from app.services import practice_plan as practice_plan_service

router = APIRouter(prefix="/coach/practice-plans", tags=["coach-edit-practice-plan"])

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
        details=[{"field": "plan_name", "message": "Practice plan name is required"}],
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
        details=[{"field": "plan_name", "message": "A practice plan with this name already exists"}],
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
    response_model=CoachPracticePlanResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createCoachPracticePlan",
    summary="Create a practice plan",
    description=(
        "Create a new active practice plan for the authenticated coach.\n\n"
        "Provide `plan_name`, `title`, or `name` for the plan title shown on the hero card. "
        "Optional `description` supplies the hero-card details copy. "
        "`drills` accepts ordered entries with at least `name`; `id` and `type` are optional when "
        "the drill is resolved from the catalog.\n\n"
        "Optional `phone` is client metadata from the status bar and is not persisted.\n\n"
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
async def create_coach_practice_plan(
    body: CoachPracticePlanCreateRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> CoachPracticePlanResponse:
    result = await practice_plan_service.create_coach_practice_plan(db, current_user, body)
    return CoachPracticePlanResponse(**result)


@router.get(
    "/{plan_id}",
    response_model=CoachPracticePlanResponse,
    operation_id="getCoachPracticePlan",
    summary="Get a practice plan by ID",
    description=(
        "Return one active practice plan owned by the authenticated coach for the "
        "**Edit Practice Plan** screen.\n\n"
        "Includes `id`, `title`, `name`, `description`, `status`, nested ordered `drills`, "
        "and `drill_count`.\n\n"
        "Returns **404** when the plan does not exist, is inactive, or is not owned by the coach.\n\n"
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
async def get_coach_practice_plan(
    plan_id: UUID = PLAN_ID_PATH,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> CoachPracticePlanResponse:
    result = await practice_plan_service.get_practice_plan(db, current_user, plan_id)
    return CoachPracticePlanResponse(**result)


@router.put(
    "/{plan_id}",
    response_model=CoachPracticePlanResponse,
    operation_id="updateCoachPracticePlan",
    summary="Update a practice plan",
    description=(
        "Update an existing practice plan owned by the authenticated coach.\n\n"
        "Provide any of `plan_name`, `title`, `name`, `description`, and/or `drills`. "
        "Optional `phone` is client metadata and is not persisted.\n\n"
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
async def update_coach_practice_plan(
    body: CoachPracticePlanUpdateRequest,
    plan_id: UUID = PLAN_ID_PATH,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> CoachPracticePlanResponse:
    result = await practice_plan_service.update_coach_practice_plan(
        db,
        current_user,
        plan_id,
        body,
    )
    return CoachPracticePlanResponse(**result)


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteCoachPracticePlan",
    summary="Delete a practice plan",
    description=(
        "Delete (deactivate) a practice plan owned by the authenticated coach.\n\n"
        "The mobile client should show a confirmation overlay before calling this endpoint.\n\n"
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
async def delete_coach_practice_plan(
    plan_id: UUID = PLAN_ID_PATH,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await practice_plan_service.delete_practice_plan(db, current_user, plan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
