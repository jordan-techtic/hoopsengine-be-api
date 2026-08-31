"""Player cancel verification endpoints."""

from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.security import decode_token
from app.models.user import User
from app.schemas.auth import CancelVerificationRequest, CancelVerificationResponse
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.player_verification import PlayerCancelVerificationInstructionsResponse
from app.services import auth as auth_service
from app.services import verification_flow as verification_flow_service

router = APIRouter(prefix="/player", tags=["player-auth"])

bearer_scheme = HTTPBearer(auto_error=False)

CANCEL_HEADING = "Cancel Verification?"
CANCEL_INSTRUCTIONS = (
    "Cancelling will stop the verification process. You will lose your progress "
    "and may need to start the signup process again."
)
CANCEL_CONSEQUENCES = (
    "Confirming cancellation will stop verification and remove your signup progress."
)
CANCEL_SUCCESS_MESSAGE = "Verification cancelled successfully."
CANCEL_DESCRIPTION = (
    "Your signup has been cancelled. Verification progress has been lost and you may need to register again."
)
INSTRUCTIONS_SUCCESS_MESSAGE = "Cancel verification instructions loaded."

CANCEL_VALIDATION_ERROR_RESPONSES = {
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
    409: openapi_error_examples(
        "Unauthenticated access or verification state conflict",
        examples={
            "unauthenticated": {
                "code": "UNAUTHENTICATED",
                "message": "Authentication is required to access this resource",
                "details": None,
            },
            "verification_already_completed": {
                "code": "VERIFICATION_ALREADY_COMPLETED",
                "message": "Your email has already been verified",
                "details": [
                    {
                        "field": "email",
                        "message": "Verification has already been completed",
                    }
                ],
            },
            "verification_not_in_progress": {
                "code": "VERIFICATION_NOT_IN_PROGRESS",
                "message": "No verification process is currently in progress",
                "details": [
                    {
                        "field": "cancel_verification",
                        "message": "Verification is not in progress or has already been cancelled",
                    }
                ],
            },
        },
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


async def require_authenticated_user_for_cancel_verification(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require a valid Bearer JWT; player cancel verification returns 409 when missing."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppException(
            code="UNAUTHENTICATED",
            message="Authentication is required to access this resource",
            status_code=409,
        )

    token = credentials.credentials

    try:
        payload = decode_token(token)
        subject = payload.get("sub")
        token_type = payload.get("type")
        if not subject or token_type != "access":
            raise AppException(
                code="UNAUTHENTICATED",
                message="Authentication is required to access this resource",
                status_code=409,
            )
        user_id = UUID(str(subject))
    except (jwt.PyJWTError, ValueError):
        raise AppException(
            code="UNAUTHENTICATED",
            message="Authentication is required to access this resource",
            status_code=409,
        ) from None

    if await auth_service.is_token_revoked(db, token, payload):
        raise AppException(
            code="UNAUTHENTICATED",
            message="Authentication is required to access this resource",
            status_code=409,
        )

    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AppException(
            code="UNAUTHENTICATED",
            message="Authentication is required to access this resource",
            status_code=409,
        )
    return user


@router.get(
    "/cancel-verification",
    response_model=PlayerCancelVerificationInstructionsResponse,
    operation_id="getPlayerCancelVerificationInstructions",
    summary="Get cancel verification instructions",
    description=(
        "Return copy and navigation targets for the **Cancel Verification** screen.\n\n"
        "Includes `heading`, `instructions`, and a `link` for the Continue Verification "
        "button. Optional query parameter `phone` accepts Figma status-bar metadata.\n\n"
        "Returns **409** when the caller is not authenticated.\n\n"
        "**Requires Bearer JWT** (`Authorization: Bearer <access_token>`)."
    ),
    responses={
        **CONFLICT_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_cancel_verification_instructions(
    phone: str | None = Query(
        default=None,
        description="Optional phone metadata from the status bar (Figma field)",
        examples=["+1-555-0100"],
    ),
    current_user: User = Depends(require_authenticated_user_for_cancel_verification),
) -> PlayerCancelVerificationInstructionsResponse:
    """Return instructional content for the cancel verification screen."""
    return PlayerCancelVerificationInstructionsResponse(
        message=INSTRUCTIONS_SUCCESS_MESSAGE,
        description=CANCEL_CONSEQUENCES,
        link=f"{settings.FRONTEND_URL.rstrip('/')}/verify-email",
        id=current_user.id,
        heading=CANCEL_HEADING,
        instructions=CANCEL_INSTRUCTIONS,
        phone=phone,
    )


@router.post(
    "/cancel-verification",
    response_model=CancelVerificationResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="playerCancelVerification",
    summary="Cancel pending player email verification",
    description=(
        "Cancel the authenticated player's ongoing email verification signup flow.\n\n"
        "Soft-deletes the unverified account, clears OTP state, and returns **201** on "
        "success with `status=cancelled`. Returns **400** when `cancel_verification` is "
        "missing, false, or the body is empty. Returns **409** when unauthenticated or when "
        "verification is already completed or not in progress.\n\n"
        "**Requires Bearer JWT** (`Authorization: Bearer <access_token>`)."
    ),
    responses={
        **CANCEL_VALIDATION_ERROR_RESPONSES,
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
    current_user: User = Depends(require_authenticated_user_for_cancel_verification),
    db: AsyncSession = Depends(get_db),
) -> CancelVerificationResponse:
    """Cancel pending verification and abandon player signup progress."""
    _validate_cancel_payload(payload)
    user = await verification_flow_service.cancel_verification(
        db,
        user=current_user,
        phone=payload.phone,
    )
    return CancelVerificationResponse(
        message=CANCEL_SUCCESS_MESSAGE,
        description=CANCEL_DESCRIPTION,
        link=f"{settings.FRONTEND_URL.rstrip('/')}/player/register",
        id=user.id,
    )
