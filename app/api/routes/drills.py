"""Drill catalog endpoints for One Drill Step-2 and practice plan search."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach
from app.core.database import get_db
from app.models.user import User
from app.schemas.drill import (
    DrillContinueRequest,
    DrillContinueResponse,
    DrillCreateRequest,
    DrillDeleteResponse,
    DrillDetailResponse,
    DrillListResponse,
    DrillMutationResponse,
    DrillSearchResponse,
    DrillUpdateRequest,
)
from app.schemas.errors import openapi_error, openapi_error_examples
from app.services import drill as drill_service

router = APIRouter(prefix="/drills", tags=["drills"])

DRILL_ID_PATH = Path(
    ...,
    description="Drill UUID",
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

SEARCH_VALIDATION_ERROR_RESPONSES = {
    400: openapi_error(
        "Missing or empty search query",
        code="VALIDATION_ERROR",
        message="Search query is required",
        details=[{"field": "q", "message": "Search query cannot be empty"}],
    ),
}

MUTATION_VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Missing or invalid drill fields",
        examples={
            "empty_drill_name": {
                "code": "VALIDATION_ERROR",
                "message": "Drill name is required",
                "details": [{"field": "drill_name", "message": "Drill name is required"}],
            },
            "empty_drill_category": {
                "code": "VALIDATION_ERROR",
                "message": "Drill category is required",
                "details": [{"field": "drill_category", "message": "Drill category is required"}],
            },
            "missing_selected_drill": {
                "code": "VALIDATION_ERROR",
                "message": "Selected drill is required",
                "details": [
                    {
                        "field": "selected_drill_id",
                        "message": "Select a drill before continuing",
                    }
                ],
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
        code="DRILL_ALREADY_EXISTS",
        message="A drill with this name already exists",
        details=[{"field": "drill_name", "message": "A drill with this name already exists"}],
    ),
}

NOT_FOUND_ERROR_RESPONSE = {
    404: openapi_error(
        "Drill not found",
        code="DRILL_NOT_FOUND",
        message="Drill not found",
        details=[{"field": "id", "message": "Drill not found"}],
    ),
}


@router.get(
    "",
    response_model=DrillListResponse,
    operation_id="listDrills",
    summary="List drills for One Drill Step-2",
    description=(
        "Return approved catalog drills for the **One Drill Step-2** drill picker.\n\n"
        "Optional query parameters filter by name:\n\n"
        "- `search` — search term\n"
        "- `full_name` — Figma alias for **Search drills by name...**\n"
        "- `q` — legacy alias used by practice-plan search\n\n"
        "When no search term is provided, all approved catalog drills are returned.\n\n"
        "Each drill includes `id`, `name`, `category`, `duration` (seconds), and optional `image`.\n\n"
        "Optional `phone` is client metadata and is not persisted.\n\n"
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
            "Drills table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Drill operations are temporarily unavailable",
        ),
    },
)
async def list_drills(
    search: str | None = Query(
        default=None,
        description="Optional case-insensitive drill name filter",
        examples=["warm"],
    ),
    full_name: str | None = Query(
        default=None,
        description="Figma search input (`Search drills by name...`)",
        examples=["Jane Doe"],
    ),
    q: str | None = Query(
        default=None,
        description="Legacy search alias",
        examples=["throw"],
    ),
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    ),
    _: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> DrillListResponse:
    result = await drill_service.list_drills(db, search=search, full_name=full_name, q=q)
    return DrillListResponse(**result)


@router.post(
    "/continue",
    response_model=DrillContinueResponse,
    operation_id="continueOneDrillWithSelectedDrill",
    summary="Continue One Drill flow after drill selection",
    description=(
        "Persist the selected drill on the active One Drill session and advance to Step 3.\n\n"
        "**Required body field:** `selected_drill_id`.\n\n"
        "Optional `full_name` and `phone` are client metadata and are not persisted.\n\n"
        "Returns **200** when the drill is selected successfully.\n\n"
        "Returns **400** when `selected_drill_id` is missing or Step 1 player selection was not completed.\n\n"
        "Returns **404** when the drill does not exist.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **MUTATION_VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Session table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Session recording is temporarily unavailable",
        ),
    },
)
async def continue_one_drill(
    body: DrillContinueRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> DrillContinueResponse:
    result = await drill_service.continue_with_drill(db, current_user, body)
    return DrillContinueResponse(**result)


@router.get(
    "/search",
    response_model=DrillSearchResponse,
    operation_id="searchDrills",
    summary="Search drills by name (practice plan picker)",
    description=(
        "Search active drills by name for the Create and Edit Practice Plan drill pickers.\n\n"
        "Provide the `q` query parameter with a non-empty search term. "
        "Only approved/active catalog drills are returned.\n\n"
        "Returns **400** when `q` is missing or blank.\n\n"
        "An empty `drills` array is a valid success response when no drills match.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **SEARCH_VALIDATION_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Drills table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Drill search is temporarily unavailable",
        ),
    },
)
async def search_drills(
    q: str = Query(
        default="",
        description="Case-insensitive drill name search term",
        examples=["warm"],
    ),
    _: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> DrillSearchResponse:
    result = await drill_service.search_drills(db, q)
    return DrillSearchResponse(**result)


@router.get(
    "/{drill_id}",
    response_model=DrillDetailResponse,
    operation_id="getDrillDetail",
    summary="Get drill details",
    description=(
        "Return drill details for the **One Drill Step-2** screen.\n\n"
        "Includes `id`, `name`, `category`, `duration`, optional `image`, and helper `description`.\n\n"
        "Returns **404** when the drill is not found or is not part of the approved catalog.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        503: openapi_error(
            "Drills table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Drill operations are temporarily unavailable",
        ),
    },
)
async def get_drill_detail(
    drill_id: UUID = DRILL_ID_PATH,
    _: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> DrillDetailResponse:
    result = await drill_service.get_drill(db, drill_id)
    return DrillDetailResponse(**result)


@router.post(
    "",
    response_model=DrillMutationResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createDrill",
    summary="Create a catalog drill",
    description=(
        "Create a new drill in the approved catalog for the coach organization.\n\n"
        "**Required body fields:** `drill_name`, `drill_category`.\n\n"
        "Optional `duration` sets `time_seconds`. Optional `full_name` and `phone` are "
        "client metadata and are not persisted.\n\n"
        "Returns **201** when the drill is created.\n\n"
        "Returns **400** for missing/invalid fields.\n\n"
        "Returns **409** when a drill with the same name already exists.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **MUTATION_VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSE,
        503: openapi_error(
            "Drills table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Drill operations are temporarily unavailable",
        ),
    },
)
async def create_drill(
    body: DrillCreateRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> DrillMutationResponse:
    result = await drill_service.create_drill(db, current_user, body)
    return DrillMutationResponse(**result)


@router.put(
    "/{drill_id}",
    response_model=DrillMutationResponse,
    operation_id="updateDrill",
    summary="Update a catalog drill",
    description=(
        "Update an existing catalog drill by id.\n\n"
        "At least one of `drill_name`, `drill_category`, or `duration` must be provided.\n\n"
        "Optional `phone` and `full_name` are client metadata and are not persisted.\n\n"
        "Returns **404** when the drill is not found.\n\n"
        "Returns **409** when the updated name conflicts with an existing drill.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **MUTATION_VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSE,
        **NOT_FOUND_ERROR_RESPONSE,
        403: openapi_error(
            "Drill belongs to another organization",
            code="FORBIDDEN",
            message="You do not have permission to modify this drill",
        ),
    },
)
async def update_drill(
    body: DrillUpdateRequest,
    drill_id: UUID = DRILL_ID_PATH,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> DrillMutationResponse:
    result = await drill_service.update_drill(db, current_user, drill_id, body)
    return DrillMutationResponse(**result)


@router.delete(
    "/{drill_id}",
    response_model=DrillDeleteResponse,
    operation_id="deleteDrill",
    summary="Delete a catalog drill",
    description=(
        "Delete a catalog drill by id.\n\n"
        "Returns **404** when the drill is not found.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
    },
)
async def delete_drill(
    drill_id: UUID = DRILL_ID_PATH,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> DrillDeleteResponse:
    result = await drill_service.delete_drill(db, current_user, drill_id)
    return DrillDeleteResponse(**result)
