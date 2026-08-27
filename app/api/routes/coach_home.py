"""Coach home screen endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach
from app.core.database import get_db
from app.models.user import User
from app.schemas.coach_home import CoachHomeResponse
from app.schemas.errors import openapi_error
from app.services import coach_home as coach_home_service

router = APIRouter(prefix="/coach", tags=["coach-home"])

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
    "/home",
    response_model=CoachHomeResponse,
    operation_id="getCoachHome",
    summary="Get coach home screen data",
    description=(
        "Return aggregated home screen data for the authenticated coach.\n\n"
        "Includes total sessions, total players, recent activities, attendance records, "
        "and mobile envelope fields (`id`, `name`, `status`).\n\n"
        "Optional query parameters `phone` and `company` are client metadata.\n\n"
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
async def get_coach_home(
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    ),
    company: str | None = Query(
        default=None,
        description="Optional organization label from Col_Organization (not persisted)",
        examples=["Acme Realty"],
    ),
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> CoachHomeResponse:
    result = await coach_home_service.get_coach_home(
        db,
        current_user,
        phone=phone,
        company=company,
    )
    return CoachHomeResponse(**result)
