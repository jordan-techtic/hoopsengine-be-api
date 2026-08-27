"""Public coach registration endpoint."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.schemas.auth import RegisterRequest, RegisterResponse
from app.schemas.errors import openapi_error
from app.services import registration as registration_service

router = APIRouter(tags=["auth"])

REGISTER_SUCCESS_MESSAGE = "Registration successful. Please verify your email."
REGISTER_DESCRIPTION = "A 6-digit verification code was sent to your email."

VALIDATION_ERROR_RESPONSE = {
    400: openapi_error(
        "Invalid registration data (empty fields, password mismatch, weak password, or terms not accepted)",
        code="VALIDATION_ERROR",
        message="Password and confirm password do not match",
        details=[{"field": "confirm_password", "message": "Password and confirm password do not match"}],
    ),
    422: openapi_error(
        "Request validation failed (missing required fields or invalid email format)",
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=[{"field": "email", "message": "value is not a valid email address"}],
    ),
}

EMAIL_CONFLICT_RESPONSE = {
    409: openapi_error(
        "Email already registered",
        code="EMAIL_ALREADY_IN_USE",
        message="This email is already in use by another account",
        details=[
            {
                "field": "email",
                "message": "This email is already in use by another account",
            }
        ],
    ),
}

USERNAME_CONFLICT_RESPONSE = {
    409: openapi_error(
        "Username already taken",
        code="USERNAME_ALREADY_IN_USE",
        message="This username is already in use by another account",
        details=[
            {
                "field": "username",
                "message": "This username is already in use by another account",
            }
        ],
    ),
}


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="registerCoach",
    summary="Register a new coach",
    description=(
        "Create a new coach account from the Coach Register screen.\n\n"
        "**Public endpoint** — no authentication required.\n\n"
        "Validates required fields, password strength, password confirmation, and "
        "terms acceptance. Returns **201** with a JWT and user profile fields needed "
        "by the mobile UI (`id`, `first_name`, `last_name`, `name`, `username`, `email`, "
        "`status`, `description`, `link`).\n\n"
        "On success, a 6-digit verification code is emailed to the registered address. "
        "The coach record is created with `role=coach` and `email_confirmed_at=null` "
        "until verification completes."
    ),
    responses={
        **VALIDATION_ERROR_RESPONSE,
        **EMAIL_CONFLICT_RESPONSE,
        **USERNAME_CONFLICT_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def register_coach(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """Register a new coach and return a JWT for the verification flow."""
    result = await registration_service.register_coach(
        db,
        first_name=payload.first_name,
        last_name=payload.last_name,
        username=payload.username,
        email=str(payload.email),
        password=payload.password,
        confirm_password=payload.confirm_password,
        terms_accepted=payload.terms_accepted,
        phone=payload.phone,
    )
    user = result.user
    return RegisterResponse(
        message=REGISTER_SUCCESS_MESSAGE,
        description=REGISTER_DESCRIPTION,
        link=f"{settings.FRONTEND_URL.rstrip('/')}/verify-email",
        access_token=result.access_token,
        expires_in_hours=result.expires_in_hours,
        id=user.id,
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        name=registration_service.build_register_user_name(user),
        username=user.username or "",
        email=user.email,
    )
