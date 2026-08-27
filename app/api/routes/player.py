"""Player verification flow endpoints (cancel / continue verification)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_authenticated_user
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.auth import (
    CancelVerificationRequest,
    CancelVerificationResponse,
    ContinueVerificationResponse,
)
from app.schemas.errors import openapi_error
from app.services import verification_flow as verification_flow_service

router = APIRouter(prefix="/player", tags=["player-verification"])

CANCEL_SUCCESS_MESSAGE = "Verification cancelled successfully."
CANCEL_DESCRIPTION = (
    "Your signup has been cancelled. Verification progress has been lost and you may need to register again."
)
CONTINUE_SUCCESS_MESSAGE = "Continue with email verification."
CONTINUE_DESCRIPTION = (
    "Enter the 6-digit verification code sent to your email to complete signup."
)

AUTH_ERROR_RESPONSES = {
    403: openapi_error(
        "Missing or invalid JWT (`FORBIDDEN`)",
        code="FORBIDDEN",
        message="Authentication is required to access this resource",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error(
        "Missing cancel_verification flag, empty body, or cancel_verification is not true",
        code="VALIDATION_ERROR",
        message="cancel_verification must be true to confirm cancellation",
        details=[
            {
                "field": "cancel_verification",
                "message": "cancel_verification must be true to confirm cancellation",
            }
        ],
    ),
    422: openapi_error(
        "Request validation failed (invalid field types)",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

CONFLICT_ERROR_RESPONSES = {
    409: openapi_error(
        "Verification already completed or not in progress",
        code="VERIFICATION_NOT_IN_PROGRESS",
        message="No verification process is currently in progress",
        details=[
            {
                "field": "cancel_verification",
                "message": "Verification is not in progress or has already been cancelled",
            }
        ],
    ),
}


def _validate_cancel_payload(payload: CancelVerificationRequest) -> None:
    """Raise 400 when cancellation is not explicitly confirmed."""
    if payload.cancel_verification is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="cancel_verification is required",
            status_code=400,
            details=[
                {
                    "field": "cancel_verification",
                    "message": "cancel_verification is required",
                }
            ],
        )
    if not payload.cancel_verification:
        raise AppException(
            code="VALIDATION_ERROR",
            message="cancel_verification must be true to confirm cancellation",
            status_code=400,
            details=[
                {
                    "field": "cancel_verification",
                    "message": "cancel_verification must be true to confirm cancellation",
                }
            ],
        )


@router.post(
    "/cancel-verification",
    response_model=CancelVerificationResponse,
    operation_id="playerCancelVerification",
    summary="Cancel pending email verification",
    description=(
        "Cancel the authenticated user's ongoing email verification signup flow.\n\n"
        "**Requires Bearer JWT** (`Authorization: Bearer <access_token>`).\n\n"
        "Soft-deletes the unverified account, clears OTP state, and returns **200** on "
        "success with `status=cancelled`. Returns **400** when `cancel_verification` is "
        "missing, false, or the body is empty. Returns **403** when unauthenticated. "
        "Returns **409** when verification is already completed or not in progress."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def cancel_verification(
    payload: CancelVerificationRequest,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> CancelVerificationResponse:
    """Cancel pending verification and abandon signup progress."""
    _validate_cancel_payload(payload)
    user = await verification_flow_service.cancel_verification(
        db,
        user=current_user,
        phone=payload.phone,
    )
    return CancelVerificationResponse(
        message=CANCEL_SUCCESS_MESSAGE,
        description=CANCEL_DESCRIPTION,
        link=f"{settings.FRONTEND_URL.rstrip('/')}/register",
        id=user.id,
    )


@router.get(
    "/continue-verification",
    response_model=ContinueVerificationResponse,
    operation_id="playerContinueVerification",
    summary="Continue pending email verification",
    description=(
        "Resume the authenticated user's email verification signup flow.\n\n"
        "**Requires Bearer JWT** (`Authorization: Bearer <access_token>`).\n\n"
        "Returns **200** with `status=pending_verification` and a link to the verification "
        "screen. Optional `phone` query parameter accepts status-bar metadata from the mobile "
        "client. Returns **403** when unauthenticated. Returns **409** when verification is "
        "already completed or not in progress."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def continue_verification(
    phone: str | None = Query(
        default=None,
        description="Optional phone metadata from the status bar (Figma field)",
        examples=["+1-555-0100"],
    ),
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> ContinueVerificationResponse:
    """Return pending verification state so the client can resume the flow."""
    user = await verification_flow_service.continue_verification(db, user=current_user)
    return ContinueVerificationResponse(
        message=CONTINUE_SUCCESS_MESSAGE,
        description=CONTINUE_DESCRIPTION,
        link=f"{settings.FRONTEND_URL.rstrip('/')}/verify-email",
        id=user.id,
        email=user.email,
        phone=phone,
    )
