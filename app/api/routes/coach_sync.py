"""Coach offline sync endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach
from app.core.database import get_db
from app.models.user import User
from app.schemas.coach_sync import (
    CoachClearCacheRequest,
    CoachSyncActionResponse,
    CoachSyncPreferencesResponse,
    CoachSyncPreferencesUpdateRequest,
    CoachSyncTriggerRequest,
)
from app.schemas.errors import openapi_error
from app.services import coach_sync as coach_sync_service

router = APIRouter(prefix="/coach", tags=["coach-sync"])

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


@router.post(
    "/sync",
    response_model=CoachSyncActionResponse,
    operation_id="triggerCoachSync",
    summary="Trigger coach data sync",
    description=(
        "Trigger the sync process for the authenticated coach (**Sync Now**).\n\n"
        "Optional `phone` is client metadata from the status bar and is not persisted.\n\n"
        "Returns **409** when a sync is already in progress (for example while pending "
        "uploads are still being processed).\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        409: openapi_error(
            "Sync already in progress",
            code="SYNC_IN_PROGRESS",
            message="A sync operation is already in progress",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def trigger_coach_sync(
    body: CoachSyncTriggerRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> CoachSyncActionResponse:
    result = await coach_sync_service.trigger_sync(db, current_user, phone=body.phone)
    return CoachSyncActionResponse(**result)


@router.post(
    "/clear-cache",
    response_model=CoachSyncActionResponse,
    operation_id="clearCoachLocalCache",
    summary="Clear coach local cache metadata",
    description=(
        "Acknowledge clearing local cache for the authenticated coach.\n\n"
        "Resets server-side sync-in-progress metadata.\n\n"
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
async def clear_coach_local_cache(
    body: CoachClearCacheRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> CoachSyncActionResponse:
    result = await coach_sync_service.clear_local_cache(db, current_user, phone=body.phone)
    return CoachSyncActionResponse(**result)


@router.get(
    "/sync/preferences",
    response_model=CoachSyncPreferencesResponse,
    operation_id="getCoachSyncPreferences",
    summary="Get coach sync preferences",
    description=(
        "Return sync preferences for the authenticated coach.\n\n"
        "Optional query parameters `phone` and `local_storage_used` are client metadata.\n\n"
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
async def get_coach_sync_preferences(
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    ),
    local_storage_used: str | None = Query(
        default=None,
        description="Optional local storage usage label echoed in the response (not persisted)",
        examples=["2.4 GB / 8 GB"],
    ),
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> CoachSyncPreferencesResponse:
    result = await coach_sync_service.get_sync_preferences(
        db,
        current_user,
        phone=phone,
        local_storage_used=local_storage_used,
    )
    return CoachSyncPreferencesResponse(**result)


@router.put(
    "/sync/preferences",
    response_model=CoachSyncPreferencesResponse,
    operation_id="updateCoachSyncPreferences",
    summary="Update coach sync preferences",
    description=(
        "Update auto sync and sync frequency preferences.\n\n"
        "Returns **400** for empty or non-numeric sync frequency values.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        400: openapi_error(
            "Invalid sync preference values",
            code="VALIDATION_ERROR",
            message="Sync frequency must include a numeric value",
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
async def update_coach_sync_preferences(
    body: CoachSyncPreferencesUpdateRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> CoachSyncPreferencesResponse:
    result = await coach_sync_service.update_sync_preferences(db, current_user, body)
    return CoachSyncPreferencesResponse(**result)
