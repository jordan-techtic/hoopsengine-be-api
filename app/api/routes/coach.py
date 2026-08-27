"""Coach authentication and verification flow endpoints."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_authenticated_user
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.auth import (
    CancelVerificationRequest,
    CancelVerificationResponse,
    CoachForgotPasswordRequest,
    CoachForgotPasswordResponse,
    CoachLoginRequest,
    CoachLoginResponse,
    ContinueVerificationResponse,
)
from app.schemas.errors import openapi_error
from app.services import auth as auth_service
from app.services import verification_flow as verification_flow_service

router = APIRouter(prefix="/coach", tags=["coach-auth"])

FORGOT_PASSWORD_SUCCESS_MESSAGE = "Password reset link has been sent to your email."
FORGOT_PASSWORD_DESCRIPTION = "Check your inbox for instructions to reset your password."
CANCEL_SUCCESS_MESSAGE = "Verification cancelled successfully."
CANCEL_DESCRIPTION = (
    "Your signup has been cancelled. Verification progress has been lost and you may need to register again."
)
CONTINUE_SUCCESS_MESSAGE = "Continue with email verification."
CONTINUE_DESCRIPTION = (
    "Enter the 6-digit verification code sent to your email to complete signup."
)

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error(
        "Missing email/username or password, or empty password",
        code="VALIDATION_ERROR",
        message="Password is required",
        details=[{"field": "password", "message": "Password is required"}],
    ),
    422: openapi_error(
        "Request validation failed (invalid email format on forgot-password)",
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=[{"field": "email", "message": "value is not a valid email address"}],
    ),
}

INVALID_CREDENTIALS_RESPONSE = {
    401: openapi_error(
        "Invalid email/username or password",
        code="INVALID_CREDENTIALS",
        message="Invalid email or password",
    ),
}

NOT_FOUND_RESPONSE = {
    404: openapi_error(
        "Coach account not found for forgot-password email",
        code="USER_NOT_FOUND",
        message="We couldn't find an account with that email. Please check the email address and try again.",
    ),
}

AUTH_ERROR_RESPONSES = {
    403: openapi_error(
        "Missing or invalid JWT (`FORBIDDEN`)",
        code="FORBIDDEN",
        message="Authentication is required to access this resource",
    ),
}

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


def _validate_coach_login_payload(payload: CoachLoginRequest) -> None:
    """Raise 400 when required login fields are missing or empty."""
    if payload.email is None or not payload.email.strip():
        raise AppException(
            code="VALIDATION_ERROR",
            message="Email or username is required",
            status_code=400,
            details=[{"field": "email", "message": "Email or username is required"}],
        )
    if payload.password is None or not payload.password.strip():
        raise AppException(
            code="VALIDATION_ERROR",
            message="Password is required",
            status_code=400,
            details=[{"field": "password", "message": "Password is required"}],
        )


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
    "/login",
    response_model=CoachLoginResponse,
    operation_id="coachLogin",
    summary="Coach login",
    description=(
        "Authenticate a verified coach using an email address or username and password.\n\n"
        "**Public endpoint** — no authentication required.\n\n"
        "Returns **200** with a JWT on success. Set `remember_me=true` for a longer-lived "
        "token (`REMEMBER_ME_TOKEN_EXPIRE_HOURS`). Returns **401** for invalid credentials "
        "or unverified email. Returns **400** when email/username or password is missing."
    ),
    responses={
        **VALIDATION_ERROR_RESPONSES,
        **INVALID_CREDENTIALS_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def coach_login(
    payload: CoachLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> CoachLoginResponse:
    """Authenticate a coach and return a JWT access token."""
    _validate_coach_login_payload(payload)
    result = await auth_service.login_coach(
        db,
        payload.email.strip(),
        payload.password,
        remember_me=payload.remember_me,
    )
    if result is None:
        raise AppException(
            code="INVALID_CREDENTIALS",
            message="Invalid email or password",
            status_code=401,
        )
    return result


@router.post(
    "/forgot-password",
    response_model=CoachForgotPasswordResponse,
    operation_id="coachForgotPassword",
    summary="Coach forgot password",
    description=(
        "Initiate the password recovery process for a coach account.\n\n"
        "**Public endpoint** — no authentication required.\n\n"
        "Sends a password reset link to the coach's registered email. Returns **404** "
        "when no matching coach account exists. The response includes a `link` to the "
        "password reset page for the Forgot Password UI flow."
    ),
    responses={
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def coach_forgot_password(
    payload: CoachForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> CoachForgotPasswordResponse:
    """Send a password reset email to the coach account."""
    reset_token = await auth_service.request_coach_password_reset(db, str(payload.email))
    if reset_token is None:
        raise AppException(
            code="USER_NOT_FOUND",
            message="We couldn't find an account with that email. Please check the email address and try again.",
            status_code=404,
        )

    response = CoachForgotPasswordResponse(
        message=FORGOT_PASSWORD_SUCCESS_MESSAGE,
        description=FORGOT_PASSWORD_DESCRIPTION,
        link=settings.RESET_PASSWORD_URL,
    )
    if settings.DEBUG:
        response.reset_token = reset_token
    return response


@router.post(
    "/cancel-verification",
    response_model=CancelVerificationResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="coachCancelVerification",
    summary="Cancel pending email verification",
    description=(
        "Cancel the authenticated coach's ongoing email verification signup flow.\n\n"
        "**Requires Bearer JWT** (`Authorization: Bearer <access_token>`).\n\n"
        "Soft-deletes the unverified account, clears OTP state, and returns **201** on "
        "success with `status=cancelled`. Returns **400** when `cancel_verification` is "
        "missing, false, or the body is empty. Returns **403** when unauthenticated. "
        "Returns **409** when verification is already completed or not in progress."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
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
    operation_id="coachContinueVerification",
    summary="Continue pending email verification",
    description=(
        "Resume the authenticated coach's email verification signup flow.\n\n"
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
