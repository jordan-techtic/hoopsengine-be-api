"""Coach practice plan CRUD endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_coach,
    get_current_org_admin,
    require_authenticated_user,
)
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.errors import openapi_error
from app.schemas.practice_plan import (
    PracticePlanCreateRequest,
    PracticePlanListResponse,
    PracticePlanResponse,
    PracticePlanUpdateRequest,
)
from app.schemas.practice_plan_assignment import (
    PracticePlanAssignmentListResponse,
    PracticePlanAssignmentResponse,
    PracticePlanAssignmentUpdateRequest,
    PracticePlanAssignRequest,
    PracticePlanPutRequest,
)
from app.schemas.roster import PlayerRosterSearchResponse
from app.services import practice_plan as practice_plan_service
from app.services import practice_plan_assignment as practice_plan_assignment_service
from app.services import roster as roster_service

router = APIRouter(prefix="/practice-plans", tags=["practice-plans"])

PLAN_ID_PATH = Path(
    ...,
    description="Practice plan UUID",
    examples=["11111111-2222-3333-4444-555555555555"],
)

READ_AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing, invalid, expired, or revoked JWT",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
    403: openapi_error(
        "Authentication is required to access this resource",
        code="FORBIDDEN",
        message="Authentication is required to access this resource",
    ),
}

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

ORG_ADMIN_AUTH_ERROR_RESPONSES = {
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

ASSIGNMENT_CONFLICT_RESPONSE = {
    409: openapi_error(
        "Practice plan already assigned to the selected coach",
        code="PRACTICE_PLAN_ALREADY_ASSIGNED",
        message="This practice plan is already assigned to the selected coach",
        details=[
            {
                "field": "coach_id",
                "message": "This practice plan is already assigned to the selected coach",
            }
        ],
    ),
}

ASSIGNMENT_NOT_FOUND_RESPONSE = {
    404: openapi_error(
        "Assigned practice plan not found",
        code="PRACTICE_PLAN_ASSIGNMENT_NOT_FOUND",
        message="Assigned practice plan not found",
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
        "**Create Practice Plan screen:** provide `plan_name` (or `full_name`), "
        "`selected_drills` (drill names from search), and optional `phone`.\n\n"
        "**Legacy format:** provide `name` and `drills` (each with `id`, `name`, and `type`).\n\n"
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
async def create_practice_plan(
    body: PracticePlanCreateRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> PracticePlanResponse:
    result = await practice_plan_service.create_practice_plan(db, current_user, body)
    return PracticePlanResponse(**result)


@router.get(
    "",
    response_model=PracticePlanListResponse | PracticePlanAssignmentListResponse,
    operation_id="listPracticePlans",
    summary="List active practice plans",
    description=(
        "Return practice plans for the authenticated user.\n\n"
        "**Organization admins** receive available org plans in `plans` plus active "
        "assignments in `assignments` (each with hero-card fields: `title`, `name`, "
        "`description`, `image`, `drill_count`, `coach_name`, `frequency`, `start_date`).\n\n"
        "**Coaches and other authenticated users** receive active practice plans in `plans` "
        "only. Coaches see plans they created; other users see all active org plans.\n\n"
        "An empty `plans` or `assignments` array is a valid empty state.\n\n"
        "**Requires authenticated JWT**."
    ),
    responses={
        **READ_AUTH_ERROR_RESPONSES,
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
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> PracticePlanListResponse | PracticePlanAssignmentListResponse:
    if current_user.role == UserRole.ORG_ADMIN.value:
        result = await practice_plan_assignment_service.list_org_practice_plan_assignments(
            db,
            current_user,
        )
        return PracticePlanAssignmentListResponse(**result)
    result = await practice_plan_service.list_active_practice_plans(db, current_user)
    return PracticePlanListResponse(**result)


@router.post(
    "/assign",
    response_model=PracticePlanAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="assignPracticePlan",
    summary="Assign a practice plan to a coach or team",
    description=(
        "Assign an active practice plan to a coach (and optional team) in the authenticated "
        "organization admin's organization.\n\n"
        "**Required body fields:** `coach_id`, `plan_id`, `start_date`. Optional `team_id` and "
        "`frequency`. Optional `phone` is client metadata from the status bar and is not persisted.\n\n"
        "Returns **201** on success. Returns **409** when the same plan is already assigned to "
        "the coach. Returns **400** when required fields are missing or references are invalid.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **ORG_ADMIN_AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **ASSIGNMENT_CONFLICT_RESPONSE,
        **ASSIGNMENT_NOT_FOUND_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Practice plan assignment tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Practice plan assignment operations are temporarily unavailable",
        ),
    },
)
async def assign_practice_plan(
    body: PracticePlanAssignRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> PracticePlanAssignmentResponse:
    """Assign a practice plan from the Organization Admin Assign Practice Plan screen."""
    result = await practice_plan_assignment_service.assign_practice_plan(db, current_user, body)
    return PracticePlanAssignmentResponse(**result)


@router.get(
    "/search",
    response_model=PlayerRosterSearchResponse,
    operation_id="searchPracticePlanRoster",
    summary="Search team roster",
    description=(
        "Search active players in the team roster by name or jersey number for the "
        "**Practice Plans** screen.\n\n"
        "Provide the `q` query parameter with a non-empty search term matching "
        "player first name, last name, full name, or jersey number.\n\n"
        "Returns **400** when `q` is missing or blank.\n\n"
        "An empty `players` array is a valid success response when no players match.\n\n"
        "**Requires authenticated JWT**."
    ),
    responses={
        **READ_AUTH_ERROR_RESPONSES,
        400: openapi_error(
            "Missing or empty search query",
            code="VALIDATION_ERROR",
            message="Search query is required",
            details=[{"field": "q", "message": "Search query cannot be empty"}],
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Players table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Roster search is temporarily unavailable",
        ),
    },
)
async def search_team_roster(
    q: str = Query(
        default="",
        description="Player name or jersey number search term",
        examples=["23"],
    ),
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> PlayerRosterSearchResponse:
    result = await roster_service.search_team_roster(db, current_user, q)
    return PlayerRosterSearchResponse(**result)


@router.put(
    "/{plan_id}",
    response_model=PracticePlanResponse | PracticePlanAssignmentResponse,
    operation_id="updatePracticePlan",
    summary="Update a practice plan or assignment",
    description=(
        "Update an existing practice plan or assignment.\n\n"
        "**Organization admins** update an assignment using `coach_id`, `team_id`, `plan_id`, "
        "`start_date`, and/or `frequency`. The `{plan_id}` path segment is the assignment UUID.\n\n"
        "**Coaches** update a owned practice plan using `name` and/or `drills`. The `{plan_id}` "
        "path segment is the practice plan UUID.\n\n"
        "Optional `phone` is client metadata and is not persisted.\n\n"
        "Returns **404** when the target record does not exist. Returns **409** when an org-admin "
        "update would duplicate an assignment.\n\n"
        "**Requires authenticated JWT** (organization admin or verified coach)."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **ORG_ADMIN_AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSE,
        **ASSIGNMENT_CONFLICT_RESPONSE,
        **NOT_FOUND_ERROR_RESPONSE,
        **ASSIGNMENT_NOT_FOUND_RESPONSE,
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
    body: PracticePlanPutRequest,
    plan_id: UUID = PLAN_ID_PATH,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> PracticePlanResponse | PracticePlanAssignmentResponse:
    if current_user.role == UserRole.ORG_ADMIN.value:
        assignment_payload = PracticePlanAssignmentUpdateRequest(
            coach_id=body.coach_id,
            team_id=body.team_id,
            plan_id=body.plan_id,
            start_date=body.start_date,
            frequency=body.frequency,
            phone=body.phone,
        )
        result = await practice_plan_assignment_service.update_practice_plan_assignment(
            db,
            current_user,
            plan_id,
            assignment_payload,
        )
        return PracticePlanAssignmentResponse(**result)

    if current_user.role != UserRole.COACH.value:
        raise AppException(
            code="FORBIDDEN",
            message="You do not have permission to access this resource",
            status_code=403,
        )
    if current_user.email_confirmed_at is None:
        raise AppException(
            code="FORBIDDEN",
            message="Email verification is required to access this resource",
            status_code=403,
        )

    coach_payload = PracticePlanUpdateRequest(
        name=body.name,
        drills=body.drills,
        phone=body.phone,
    )
    result = await practice_plan_service.update_practice_plan(
        db,
        current_user,
        plan_id,
        coach_payload,
    )
    return PracticePlanResponse(**result)


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deletePracticePlan",
    summary="Delete a practice plan or assignment",
    description=(
        "Delete a practice plan or assignment.\n\n"
        "**Organization admins** remove an assignment. The `{plan_id}` path segment is the "
        "assignment UUID. Returns **204 No Content** on success.\n\n"
        "**Coaches** deactivate an owned practice plan. The `{plan_id}` path segment is the "
        "practice plan UUID.\n\n"
        "Returns **404** when the target record does not exist.\n\n"
        "**Requires authenticated JWT** (organization admin or verified coach)."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **ORG_ADMIN_AUTH_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        **ASSIGNMENT_NOT_FOUND_RESPONSE,
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
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if current_user.role == UserRole.ORG_ADMIN.value:
        await practice_plan_assignment_service.delete_practice_plan_assignment(
            db,
            current_user,
            plan_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    if current_user.role != UserRole.COACH.value:
        raise AppException(
            code="FORBIDDEN",
            message="You do not have permission to access this resource",
            status_code=403,
        )
    if current_user.email_confirmed_at is None:
        raise AppException(
            code="FORBIDDEN",
            message="Email verification is required to access this resource",
            status_code=403,
        )

    await practice_plan_service.delete_practice_plan(db, current_user, plan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
