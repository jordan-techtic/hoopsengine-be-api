"""Home screen split endpoints used by mobile acceptance criteria."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach
from app.core.database import get_db
from app.models.user import User
from app.schemas.coach_home import (
    HomeActivitiesResponse,
    HomeNotificationsResponse,
    HomeUserInfoResponse,
)
from app.schemas.errors import openapi_error
from app.services import coach_home as coach_home_service

router = APIRouter(prefix="/home", tags=["home"])

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
    "/activities",
    response_model=HomeActivitiesResponse,
    operation_id="getHomeActivities",
    summary="Get home activities",
    description=(
        "Return up to 10 recent activities for the authenticated coach.\n\n"
        "Includes pagination metadata (`limit`, `count`) and mobile envelope fields.\n\n"
        "Returns **404** when no activities exist.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        404: openapi_error(
            "No activities found",
            code="ACTIVITIES_NOT_FOUND",
            message="No activities found for this user",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_home_activities(
    limit: int = Query(
        default=10,
        ge=1,
        le=10,
        description="Maximum number of activities to return (paginated, max 10)",
        examples=[10],
    ),
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> HomeActivitiesResponse:
    result = await coach_home_service.get_home_activities(db, current_user, limit=limit)
    return HomeActivitiesResponse(**result)


@router.get(
    "/user-info",
    response_model=HomeUserInfoResponse,
    operation_id="getHomeUserInfo",
    summary="Get home user info",
    description=(
        "Return user-specific home screen information for the authenticated coach.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        404: openapi_error(
            "User not found",
            code="USER_NOT_FOUND",
            message="User not found",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_home_user_info(
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> HomeUserInfoResponse:
    result = await coach_home_service.get_home_user_info(db, current_user)
    return HomeUserInfoResponse(**result)


@router.get(
    "/notifications",
    response_model=HomeNotificationsResponse,
    operation_id="getHomeNotifications",
    summary="Get home notifications",
    description=(
        "Return notifications for the authenticated coach.\n\n"
        "Returns **404** when no notifications exist.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        404: openapi_error(
            "No notifications found",
            code="NOTIFICATIONS_NOT_FOUND",
            message="No notifications found for this user",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_home_notifications(
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> HomeNotificationsResponse:
    result = await coach_home_service.get_home_notifications(db, current_user)
    return HomeNotificationsResponse(**result)
