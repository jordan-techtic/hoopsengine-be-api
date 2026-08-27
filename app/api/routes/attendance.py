"""Coach Attendance screen endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach
from app.core.database import get_db
from app.models.user import User
from app.schemas.attendance import (
    AttendancePlayerSearchResponse,
    AttendanceStartPracticeRequest,
    AttendanceStartPracticeResponse,
    AttendanceSummaryResponse,
)
from app.schemas.errors import openapi_error
from app.services import attendance as attendance_service

router = APIRouter(prefix="/attendance", tags=["attendance"])

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
        "Missing or invalid attendance fields",
        code="VALIDATION_ERROR",
        message="Search query is required",
        details=[
            {
                "field": "full_name",
                "message": "Provide full_name or search_query to search players",
            }
        ],
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}


@router.get(
    "/players/search",
    response_model=AttendancePlayerSearchResponse,
    operation_id="searchAttendancePlayers",
    summary="Search attendance players",
    description=(
        "Search active players by name or jersey number for the **Attendance** screen.\n\n"
        "**Requires authenticated verified coach JWT**.\n\n"
        "Accepts Figma field `full_name` and/or `search_query`. Optional `phone` is client "
        "metadata and is not persisted.\n\n"
        "Returns **400** when both search fields are empty.\n\n"
        "Only **active** players in the coach organization are returned, each with an "
        "`status` of `present` or `absent` for the current attendance session."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        503: openapi_error(
            "Players or practice session tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Attendance operations are temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def search_attendance_players(
    full_name: str | None = Query(
        default=None,
        description="Figma player search input (name or jersey number)",
        examples=["Alex Martinez"],
    ),
    search_query: str | None = Query(
        default=None,
        description="Alternative search text matching ticket data field search_query",
        examples=["12"],
    ),
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    ),
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> AttendancePlayerSearchResponse:
    """Search players for attendance marking."""
    _ = phone
    result = await attendance_service.search_attendance_players(
        db,
        current_user,
        search_query=search_query,
        full_name=full_name,
    )
    return AttendancePlayerSearchResponse(**result)


@router.get(
    "/summary",
    response_model=AttendanceSummaryResponse,
    operation_id="getAttendanceSummary",
    summary="Get attendance summary",
    description=(
        "Return the attendance summary row and full active player list for the "
        "**Attendance** screen.\n\n"
        "**Requires authenticated verified coach JWT**.\n\n"
        "The `attendance_summary` object includes `present_count` and `total_count`. "
        "Each player item includes `name`, `jersey_number`, and `status`.\n\n"
        "Only **active** players are included."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        503: openapi_error(
            "Players or practice session tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Attendance operations are temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_attendance_summary(
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> AttendanceSummaryResponse:
    """Retrieve attendance summary and player statuses."""
    result = await attendance_service.get_attendance_summary(db, current_user)
    return AttendanceSummaryResponse(**result)


@router.post(
    "/start-practice",
    response_model=AttendanceStartPracticeResponse,
    status_code=status.HTTP_200_OK,
    operation_id="startAttendancePractice",
    summary="Start practice from attendance",
    description=(
        "Mark selected players as present and start the practice session.\n\n"
        "**Requires authenticated verified coach JWT**.\n\n"
        "Accepts `present_player_ids` listing the players who should be marked present. "
        "Optional `phone` is client metadata and is not persisted.\n\n"
        "Returns **200** on success with updated `attendance_summary` and player list.\n\n"
        "Returns **400** when any `present_player_ids` value is not an active roster player."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        503: openapi_error(
            "Players or practice session tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Attendance operations are temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def start_attendance_practice(
    body: AttendanceStartPracticeRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> AttendanceStartPracticeResponse:
    """Start practice after attendance confirmation."""
    result = await attendance_service.start_attendance_practice(db, current_user, body)
    return AttendanceStartPracticeResponse(**result)
