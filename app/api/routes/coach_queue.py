"""Coach sync queue endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach
from app.core.database import get_db
from app.models.user import User
from app.schemas.coach_queue import (
    CoachQueueListResponse,
    CoachQueueUpdateRequest,
    CoachQueueUpdateResponse,
)
from app.schemas.errors import openapi_error, openapi_error_examples
from app.services import coach_queue as coach_queue_service

router = APIRouter(prefix="/coach/queue", tags=["coach-queue"])

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

GET_VALIDATION_ERROR_RESPONSES = {
    400: openapi_error(
        "Invalid queue query parameters",
        code="VALIDATION_ERROR",
        message="Invalid status_filter value",
        details=[
            {
                "field": "status_filter",
                "message": "status_filter must be pending_sync, synced, or all",
            }
        ],
    ),
}

POST_VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Missing or invalid queue update fields",
        examples={
            "invalid_item_type": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid item_type value",
                "details": [
                    {
                        "field": "item_type",
                        "message": "item_type must be practice_session or session_data",
                    }
                ],
            },
            "invalid_status": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid queue status value",
                "details": [
                    {
                        "field": "status",
                        "message": "status must be pending_sync, synced, or failed",
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

NOT_FOUND_ERROR_RESPONSE = {
    404: openapi_error(
        "Queue item not found",
        code="QUEUE_ITEM_NOT_FOUND",
        message="Queue item not found",
    ),
}


@router.get(
    "",
    response_model=CoachQueueListResponse,
    operation_id="listCoachQueueItems",
    summary="List coach queue items pending sync",
    description=(
        "Return locally saved items pending synchronization for the **Queue** screen.\n\n"
        "Includes a header `title` such as **3 Items Pending Sync**, the coach `name`, "
        "and each queue row with `id`, `title`, `name`, and `status`.\n\n"
        "Optional query parameter `status_filter` accepts `pending_sync` (default behavior), "
        "`synced`, or `all`.\n\n"
        "Optional `phone` is client metadata from the status bar and is not persisted.\n\n"
        "Returns **400** when `status_filter` is invalid.\n\n"
        "Returns **200** with an empty `items` array when nothing is pending.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **GET_VALIDATION_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Client tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Queue operations are temporarily unavailable",
        ),
    },
)
async def list_coach_queue_items(
    status_filter: str | None = Query(
        default=None,
        description="Optional filter (`pending_sync`, `synced`, or `all`)",
        examples=["pending_sync"],
    ),
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    ),
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> CoachQueueListResponse:
    result = await coach_queue_service.list_queue_items(
        db,
        current_user,
        status_filter=status_filter,
        phone=phone,
    )
    return CoachQueueListResponse(**result)


@router.post(
    "",
    response_model=CoachQueueUpdateResponse,
    operation_id="updateCoachQueueItem",
    summary="Update a coach queue item sync status",
    description=(
        "Update the synchronization status of a queue item.\n\n"
        "**Required body fields:** `item_id`, `item_type`, and `status`.\n\n"
        "`item_type` must be `practice_session` or `session_data`.\n\n"
        "`status` must be `pending_sync`, `synced`, or `failed`.\n\n"
        "Optional `phone` is client metadata and is not persisted.\n\n"
        "Returns **200** when the item is updated successfully.\n\n"
        "Returns **400** for invalid fields.\n\n"
        "Returns **404** when the item does not exist or is not owned by the coach.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **POST_VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Client tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Queue operations are temporarily unavailable",
        ),
    },
)
async def update_coach_queue_item(
    body: CoachQueueUpdateRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> CoachQueueUpdateResponse:
    result = await coach_queue_service.update_queue_item(db, current_user, body)
    return CoachQueueUpdateResponse(**result)
