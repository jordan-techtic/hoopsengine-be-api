"""Coach session mode selection and recording endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.session_record import (
    SessionModeDetailResponse,
    SessionModesResponse,
    SessionRecordCreateRequest,
    SessionRecordResponse,
    SessionRecordUpdateRequest,
)
from app.schemas.one_drill_session import (
    OneDrillSessionCreateRequest,
    OneDrillSessionResponse,
    OneDrillSessionUpdateRequest,
    OneDrillSessionsSummaryResponse,
)
from app.schemas.session_summary import (
    SessionActionRequest,
    SessionActionResponse,
    SessionSummaryResponse,
)
from app.services import one_drill_session as one_drill_session_service
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
    description="Practice session UUID returned from POST /sessions or POST /sessions/record",
    examples=["11111111-2222-3333-4444-555555555555"],
)

ONE_DRILL_VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Missing or invalid session metrics",
        examples={
            "missing_player": {
                "code": "VALIDATION_ERROR",
                "message": "Player is required",
                "details": [{"field": "player", "message": "Player is required"}],
            },
            "missing_drill": {
                "code": "VALIDATION_ERROR",
                "message": "Drill is required",
                "details": [{"field": "drill", "message": "Drill is required"}],
            },
            "makes_exceed_attempts": {
                "code": "VALIDATION_ERROR",
                "message": "Session metrics are invalid",
                "details": [{"field": "makes", "message": "Makes cannot exceed attempts"}],
            },
            "empty_update": {
                "code": "VALIDATION_ERROR",
                "message": "At least one metric field must be provided",
                "details": [
                    {
                        "field": "makes",
                        "message": "Provide makes, attempts, and/or free throw metrics to update",
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

ONE_DRILL_NOT_FOUND_RESPONSES = {
    404: openapi_error_examples(
        "Session, player, or drill not found",
        examples={
            "session_not_found": {
                "code": "SESSION_NOT_FOUND",
                "message": "Session not found",
                "details": None,
            },
            "player_not_found": {
                "code": "PLAYER_NOT_FOUND",
                "message": "Player not found",
                "details": [{"field": "player", "message": "Player not found in your organization"}],
            },
            "drill_not_found": {
                "code": "DRILL_NOT_FOUND",
                "message": "Drill not found",
                "details": [{"field": "drill", "message": "Drill not found"}],
            },
        },
    ),
}


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
    summary="Record a session for a selected drill or mode",
    description=(
        "Create a new `practice_sessions` row after the coach selects a recording mode.\n\n"
        "**Required body field:** `session_mode`.\n\n"
        "When `session_mode` is `one_drill`, **`drill_id`** and **`session_data`** "
        "(reps, time, performance) are also required. Optional `user_id` must match the "
        "authenticated coach when provided.\n\n"
        "Optional `session_details.description` stores coach notes. Optional `phone` is "
        "client metadata from the status bar and is not persisted.\n\n"
        "Returns **400** when One Drill required fields are missing or invalid.\n\n"
        "Returns **404** when the selected drill does not exist.\n\n"
        "Returns **409** when the coach already recorded the same drill today, or when "
        "an active session mode is already recorded for today.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        400: openapi_error_examples(
            "Missing One Drill fields or invalid coach context",
            examples={
                "missing_drill_id": {
                    "code": "VALIDATION_ERROR",
                    "message": "Drill selection is required for One Drill sessions",
                    "details": [
                        {"field": "drill_id", "message": "drill_id is required for one_drill sessions"}
                    ],
                },
                "missing_session_data": {
                    "code": "VALIDATION_ERROR",
                    "message": "Session data is required for One Drill sessions",
                    "details": [
                        {
                            "field": "session_data",
                            "message": "session_data with reps, time, and performance is required",
                        }
                    ],
                },
                "missing_org": {
                    "code": "VALIDATION_ERROR",
                    "message": "Coach must belong to an organization before recording sessions",
                    "details": [
                        {
                            "field": "org_id",
                            "message": "Coach must belong to an organization before recording sessions",
                        }
                    ],
                },
            },
        ),
        404: openapi_error(
            "Selected drill not found",
            code="DRILL_NOT_FOUND",
            message="Selected drill was not found",
            details=[{"field": "drill_id", "message": "Selected drill was not found"}],
        ),
        409: openapi_error_examples(
            "Duplicate session for today",
            examples={
                "duplicate_drill": {
                    "code": "SESSION_ALREADY_RECORDED",
                    "message": "A session for this drill has already been recorded today",
                    "details": [
                        {
                            "field": "drill_id",
                            "message": "A session for this drill has already been recorded today",
                        }
                    ],
                },
                "active_session": {
                    "code": "SESSION_MODE_ALREADY_RECORDED",
                    "message": "An active session mode is already recorded for today",
                    "details": [
                        {
                            "field": "session_mode",
                            "message": "An active session mode is already recorded for today",
                        }
                    ],
                },
            },
        ),
        422: openapi_error(
            "Request validation failed (invalid session_mode or session_data shape)",
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


@router.post(
    "",
    response_model=OneDrillSessionResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createOneDrillSession",
    summary="Create a One Drill Step-3 session",
    description=(
        "Create a new One Drill practice session with player, drill, and performance metrics.\n\n"
        "**Required body fields:** `player`, `drill`, `makes`, `attempts`.\n\n"
        "Optional `free_throws_makes` and `free_throws_attempts` default to 0.\n\n"
        "Optional `phone` is client metadata from the status bar and is not persisted.\n\n"
        "Returns **201** when the session is saved successfully.\n\n"
        "Returns **400** when required fields are missing or metrics are invalid.\n\n"
        "Returns **404** when the player or drill cannot be resolved.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **ONE_DRILL_VALIDATION_ERROR_RESPONSES,
        **ONE_DRILL_NOT_FOUND_RESPONSES,
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
async def create_one_drill_session(
    body: OneDrillSessionCreateRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> OneDrillSessionResponse:
    result = await one_drill_session_service.create_one_drill_session(db, current_user, body)
    return OneDrillSessionResponse(**result)


@router.get(
    "/summary",
    response_model=OneDrillSessionsSummaryResponse,
    operation_id="listOneDrillSessionsSummary",
    summary="List One Drill session summaries",
    description=(
        "Return a summary list of One Drill sessions recorded by the authenticated coach.\n\n"
        "Each item includes `id`, `player`, `drill`, `makes`, `attempts`, free throw metrics, "
        "and session `status`.\n\n"
        "Returns **200** with an empty `sessions` array when no sessions exist.\n\n"
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
            "Client session table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Session recording is temporarily unavailable",
        ),
    },
)
async def list_one_drill_sessions_summary(
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> OneDrillSessionsSummaryResponse:
    result = await one_drill_session_service.list_one_drill_sessions_summary(db, current_user)
    return OneDrillSessionsSummaryResponse(**result)


@router.put(
    "/{session_id}",
    response_model=OneDrillSessionResponse,
    operation_id="updateOneDrillSession",
    summary="Update One Drill session metrics",
    description=(
        "Update performance metrics for an existing One Drill session.\n\n"
        "Provide at least one of `makes`, `attempts`, `free_throws_makes`, or "
        "`free_throws_attempts`.\n\n"
        "Optional `phone` is client metadata and is not persisted.\n\n"
        "Returns **200** when metrics are updated successfully.\n\n"
        "Returns **400** for invalid metrics or an empty update payload.\n\n"
        "Returns **403** when the session belongs to another coach.\n\n"
        "Returns **404** when the session does not exist.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **ONE_DRILL_VALIDATION_ERROR_RESPONSES,
        **ONE_DRILL_NOT_FOUND_RESPONSES,
        403: openapi_error(
            "Session belongs to another coach",
            code="SESSION_ACCESS_FORBIDDEN",
            message="You do not have permission to access this session",
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
async def update_one_drill_session(
    body: OneDrillSessionUpdateRequest,
    session_id: UUID = SESSION_ID_PATH,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> OneDrillSessionResponse:
    result = await one_drill_session_service.update_one_drill_session(
        db, current_user, session_id, body
    )
    return OneDrillSessionResponse(**result)


@router.get(
    "/{session_id}",
    response_model=OneDrillSessionResponse,
    operation_id="getOneDrillSession",
    summary="Get One Drill session details",
    description=(
        "Return One Drill Step-3 session details including selected `player`, `drill`, "
        "`makes`, `attempts`, and free throw metrics.\n\n"
        "The response includes the mobile envelope fields `message`, `status`, "
        "`description`, `link`, and `error`.\n\n"
        "Returns **404** when the session does not exist.\n\n"
        "Returns **403** when the session belongs to another coach.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **ONE_DRILL_NOT_FOUND_RESPONSES,
        403: openapi_error(
            "Session belongs to another coach",
            code="SESSION_ACCESS_FORBIDDEN",
            message="You do not have permission to access this session",
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
async def get_one_drill_session(
    session_id: UUID = SESSION_ID_PATH,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> OneDrillSessionResponse:
    result = await one_drill_session_service.get_one_drill_session(db, current_user, session_id)
    return OneDrillSessionResponse(**result)


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
