"""Coach sync activity endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach
from app.core.database import get_db
from app.models.user import User
from app.schemas.coach_sync_activity import (
    CoachSyncActivityResponse,
    CoachSyncActivitySaveRequest,
    CoachSyncActivitySaveResponse,
)
from app.schemas.errors import openapi_error
from app.services import coach_sync_activity as coach_sync_activity_service

router = APIRouter(prefix="/coach/sync-activity", tags=["coach-sync-activity"])

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


@router.get(
    "",
    response_model=CoachSyncActivityResponse,
    operation_id="getCoachSyncActivity",
    summary="Get coach sync activity",
    description=(
        "Return recent sync activity logs for the authenticated coach.\n\n"
        "Includes the status card fields `title` and `description`, recent activity rows, "
        "`save_status`, and optional `phone` client metadata.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_coach_sync_activity(
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    ),
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> CoachSyncActivityResponse:
    result = await coach_sync_activity_service.get_sync_activity(
        db,
        current_user,
        phone=phone,
    )
    return CoachSyncActivityResponse(**result)


@router.post(
    "/save",
    response_model=CoachSyncActivitySaveResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="saveCoachSyncActivity",
    summary="Save coach sync activity updates",
    description=(
        "Save updates to sync activity status for the authenticated coach.\n\n"
        "Returns **400** when required fields are missing or invalid.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        400: openapi_error(
            "Invalid sync activity payload",
            code="VALIDATION_ERROR",
            message="recent_activities is required",
        ),
        422: openapi_error(
            "Request body failed schema validation",
            code="VALIDATION_ERROR",
            message="Request validation failed",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def save_coach_sync_activity(
    body: CoachSyncActivitySaveRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> CoachSyncActivitySaveResponse:
    result = await coach_sync_activity_service.save_sync_activity(db, current_user, body)
    return CoachSyncActivitySaveResponse(**result)
