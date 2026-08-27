"""Coach session mode selection and recording endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error
from app.schemas.session_record import (
    SessionModeDetailResponse,
    SessionModesResponse,
    SessionRecordCreateRequest,
    SessionRecordResponse,
    SessionRecordUpdateRequest,
)
from app.schemas.session_summary import (
    SessionActionRequest,
    SessionActionResponse,
    SessionSummaryResponse,
)
from app.services import session_record as session_record_service
from app.services import session_summary as session_summary_service

router = APIRouter(prefix="/sessions", tags=["coach-sessions"])

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

SESSION_ID_PATH = Path(
    ...,
    description="Practice session UUID returned from POST /sessions/record",
    examples=["11111111-2222-3333-4444-555555555555"],
)


@router.get(
    "/modes",
    response_model=SessionModesResponse,
    operation_id="listSessionModes",
    summary="List available session recording modes",
    description=(
        "Return the selectable session modes for the **Choose Your Session Mode** screen:\n\n"
        "- `one_drill` — One Drill\n"
        "- `daily_options` — Daily Options\n"
        "- `practice_plan` — Practice Plan\n\n"
        "Each item includes a UI label and description. The response also includes "
        "`message`, `status`, `description`, `link`, and `error` fields for the mobile client.\n\n"
        "**Requires authenticated verified coach JWT** (`Authorization: Bearer <access_token>`)."
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
async def list_session_modes(
    _: User = Depends(get_current_coach),
) -> SessionModesResponse:
    modes = session_record_service.get_session_modes()
    return SessionModesResponse(
        message="Session modes loaded successfully",
        status="ready",
        description="Choose a mode to begin recording your training session",
        link=None,
        modes=modes,
    )


@router.get(
    "/modes/{mode}",
    response_model=SessionModeDetailResponse,
    operation_id="getSessionMode",
    summary="Get a session mode by identifier",
    description=(
        "Return a single session mode by its machine-readable key (e.g. `one_drill`).\n\n"
        "Returns **404** when the mode does not exist.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        404: openapi_error(
            "Unknown session mode",
            code="SESSION_MODE_NOT_FOUND",
            message="Session mode not found",
        ),
    },
)
async def get_session_mode(
    mode: str = Path(
        ...,
        description="Session mode key (`one_drill`, `daily_options`, `practice_plan`)",
        examples=["one_drill"],
    ),
    _: User = Depends(get_current_coach),
) -> SessionModeDetailResponse:
    item = session_record_service.get_mode_or_404(mode)
    return SessionModeDetailResponse(
        message="Session mode loaded successfully",
        status="ready",
        description=item.description,
        link=None,
        mode=item,
    )


@router.post(
    "/record",
    response_model=SessionRecordResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createSessionRecord",
    summary="Create a session record with selected mode",
    description=(
        "Create a new `practice_sessions` row after the coach selects a recording mode.\n\n"
        "**Required body field:** `session_mode`.\n\n"
        "Optional `session_details.description` stores coach notes. Optional `phone` is "
        "client metadata from the status bar and is not persisted.\n\n"
        "Returns **409** when the coach already has an active session for today.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        400: openapi_error(
            "Invalid session data or coach missing organization",
            code="VALIDATION_ERROR",
            message="Coach must belong to an organization before recording sessions",
            details=[
                {
                    "field": "org_id",
                    "message": "Coach must belong to an organization before recording sessions",
                }
            ],
        ),
        409: openapi_error(
            "Duplicate active session for today",
            code="SESSION_MODE_ALREADY_RECORDED",
            message="An active session mode is already recorded for today",
            details=[
                {
                    "field": "session_mode",
                    "message": "An active session mode is already recorded for today",
                }
            ],
        ),
        422: openapi_error(
            "Request validation failed (missing session_mode)",
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details=[{"field": "session_mode", "message": "Field required"}],
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Client session table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Session recording is temporarily unavailable",
        ),
    },
)
async def create_session_record(
    body: SessionRecordCreateRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> SessionRecordResponse:
    result = await session_record_service.create_session_record(db, current_user, body)
    return SessionRecordResponse(**result)


@router.put(
    "/record/{session_id}",
    response_model=SessionRecordResponse,
    operation_id="updateSessionRecord",
    summary="Update an existing session record",
    description=(
        "Update `session_mode` and/or `session_details` on an existing practice session "
        "owned by the authenticated coach.\n\n"
        "Optional `phone` is client metadata and is not persisted.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        400: openapi_error(
            "Empty update payload",
            code="VALIDATION_ERROR",
            message="At least one field must be provided to update the session record",
            details=[
                {
                    "field": "session_mode",
                    "message": "Provide session_mode and/or session_details to update",
                }
            ],
        ),
        404: openapi_error(
            "Session not found or not owned by coach",
            code="SESSION_NOT_FOUND",
            message="Session record not found",
        ),
        422: openapi_error(
            "Request validation failed",
            code="VALIDATION_ERROR",
            message="Request validation failed",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Client session table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Session recording is temporarily unavailable",
        ),
    },
)
async def update_session_record(
    body: SessionRecordUpdateRequest,
    session_id: UUID = SESSION_ID_PATH,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> SessionRecordResponse:
    result = await session_record_service.update_session_record(
        db,
        current_user,
        session_id,
        body,
    )
    return SessionRecordResponse(**result)


@router.get(
    "/{session_id}",
    response_model=SessionSummaryResponse,
    operation_id="getSessionSummary",
    summary="Get session summary with player performance metrics",
    description=(
        "Return aggregated player statistics for a practice session, including attempts, "
        "makes, shooting percentage, and free throw metrics.\n\n"
        "The response includes `session_time`, a UI `status` message, and the standard "
        "mobile envelope fields (`message`, `description`, `link`, `error`, `id`).\n\n"
        "Returns **404** when the session does not exist and **403** when the session "
        "belongs to another coach.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        403: openapi_error(
            "Session belongs to another coach",
            code="SESSION_ACCESS_FORBIDDEN",
            message="You do not have permission to access this session",
        ),
        404: openapi_error(
            "Session not found",
            code="SESSION_NOT_FOUND",
            message="Session not found",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Client session table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Session recording is temporarily unavailable",
        ),
    },
)
async def get_session_summary(
    session_id: UUID = SESSION_ID_PATH,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> SessionSummaryResponse:
    result = await session_summary_service.get_session_summary(db, current_user, session_id)
    return SessionSummaryResponse(**result)


@router.post(
    "/{session_id}/next-drill",
    response_model=SessionActionResponse,
    operation_id="advanceSessionNextDrill",
    summary="Navigate to the next drill in the session",
    description=(
        "Increment the session's `current_drill_index` and keep the session "
        "`in_progress`.\n\n"
        "Optional `phone` in the body is client metadata from the status bar and is "
        "not persisted.\n\n"
        "Returns **403** when the session belongs to another coach and **404** when "
        "the session does not exist.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        400: openapi_error(
            "Session already completed",
            code="SESSION_ALREADY_COMPLETED",
            message="This practice session has already ended",
        ),
        403: openapi_error(
            "Session belongs to another coach",
            code="SESSION_ACCESS_FORBIDDEN",
            message="You do not have permission to access this session",
        ),
        404: openapi_error(
            "Session not found",
            code="SESSION_NOT_FOUND",
            message="Session not found",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Client session table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Session recording is temporarily unavailable",
        ),
    },
)
async def advance_session_next_drill(
    body: SessionActionRequest = SessionActionRequest(),
    session_id: UUID = SESSION_ID_PATH,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> SessionActionResponse:
    result = await session_summary_service.advance_next_drill(db, current_user, session_id)
    return SessionActionResponse(**result)


@router.post(
    "/{session_id}/end-practice",
    response_model=SessionSummaryResponse,
    operation_id="endSessionPractice",
    summary="End the current practice session",
    description=(
        "Mark the practice session as `completed`, set `ended_at`, and return the "
        "final summary with player statistics.\n\n"
        "The `status` field becomes **Session Complete! Nice work, coach**.\n\n"
        "Optional `phone` in the body is client metadata and is not persisted.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        400: openapi_error(
            "Session already completed",
            code="SESSION_ALREADY_COMPLETED",
            message="This practice session has already ended",
        ),
        403: openapi_error(
            "Session belongs to another coach",
            code="SESSION_ACCESS_FORBIDDEN",
            message="You do not have permission to access this session",
        ),
        404: openapi_error(
            "Session not found",
            code="SESSION_NOT_FOUND",
            message="Session not found",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Client session table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Session recording is temporarily unavailable",
        ),
    },
)
async def end_session_practice(
    body: SessionActionRequest = SessionActionRequest(),
    session_id: UUID = SESSION_ID_PATH,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> SessionSummaryResponse:
    result = await session_summary_service.end_practice(db, current_user, session_id)
    return SessionSummaryResponse(**result)
