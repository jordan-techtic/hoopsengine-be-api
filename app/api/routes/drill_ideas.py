"""Coach drill idea submission endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach
from app.core.database import get_db
from app.models.user import User
from app.schemas.drill_idea import (
    DrillIdeaCreateRequest,
    DrillIdeaCreateResponse,
    DrillIdeaListResponse,
)
from app.schemas.errors import openapi_error, openapi_error_examples
from app.services import drill_idea as drill_idea_service

router = APIRouter(prefix="/drill-ideas", tags=["coach-drill-ideas"])

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
    400: openapi_error_examples(
        "Missing or invalid drill idea fields",
        examples={
            "missing_drill_name": {
                "code": "VALIDATION_ERROR",
                "message": "Drill name is required",
                "details": [{"field": "drill_name", "message": "Drill name is required"}],
            },
            "empty_category": {
                "code": "VALIDATION_ERROR",
                "message": "Category is required",
                "details": [{"field": "category", "message": "Category is required"}],
            },
            "invalid_difficulty": {
                "code": "VALIDATION_ERROR",
                "message": "Difficulty level must be Beginner, Intermediate, or Advanced",
                "details": [
                    {
                        "field": "difficulty_level",
                        "message": "Difficulty level must be Beginner, Intermediate, or Advanced",
                    }
                ],
            },
            "empty_instructions": {
                "code": "VALIDATION_ERROR",
                "message": "Instructions is required",
                "details": [{"field": "instructions", "message": "Instructions is required"}],
            },
        },
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

CONFLICT_ERROR_RESPONSE = {
    409: openapi_error(
        "Drill name already exists",
        code="DRILL_IDEA_ALREADY_EXISTS",
        message="A drill with this name already exists",
        details=[{"field": "drill_name", "message": "A drill with this name already exists"}],
    ),
}


@router.post(
    "",
    response_model=DrillIdeaCreateResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="submitDrillIdea",
    summary="Submit a custom drill idea",
    description=(
        "Submit a custom drill idea from the **Drill-idea submission** screen.\n\n"
        "**Required body fields:** `drill_name` (or Figma alias `full_name`), `category`, "
        "`difficulty_level`, and `instructions`.\n\n"
        "`difficulty_level` must be one of: **Beginner**, **Intermediate**, or **Advanced**.\n\n"
        "Optional `phone` is client metadata from the status bar and is not persisted.\n\n"
        "Returns **201** when the drill idea is submitted successfully.\n\n"
        "Returns **400** when required fields are missing or invalid.\n\n"
        "Returns **409** when a drill with the same name already exists.\n\n"
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
            "Drill submissions table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Drill idea submission is temporarily unavailable",
        ),
    },
)
async def submit_drill_idea(
    body: DrillIdeaCreateRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> DrillIdeaCreateResponse:
    result = await drill_idea_service.submit_drill_idea(db, current_user, body)
    return DrillIdeaCreateResponse(**result)


@router.get(
    "",
    response_model=DrillIdeaListResponse,
    operation_id="listDrillIdeas",
    summary="List submitted drill ideas",
    description=(
        "Return drill ideas submitted by coaches in the authenticated coach's organization.\n\n"
        "Each item includes `id`, `name`, `category`, `difficulty_level`, `instructions`, "
        "and review `status`.\n\n"
        "Returns **200** with an empty `drill_ideas` array when none exist.\n\n"
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
            "Drill submissions table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Drill idea submission is temporarily unavailable",
        ),
    },
)
async def list_drill_ideas(
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> DrillIdeaListResponse:
    result = await drill_idea_service.list_drill_ideas(db, current_user)
    return DrillIdeaListResponse(**result)
