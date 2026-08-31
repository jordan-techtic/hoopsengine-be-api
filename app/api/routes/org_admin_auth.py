"""Organization Admin authentication endpoints (HE-423)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.org_admin_auth import OrgAdminLoginRequest, OrgAdminLoginResponse
from app.services import org_admin_auth as org_admin_auth_service

router = APIRouter(prefix="/organization", tags=["org-admin-auth"])

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Missing username/email or password, invalid email format, or weak password",
        examples={
            "missing_username": {
                "code": "VALIDATION_ERROR",
                "message": "Username is required",
                "details": [{"field": "username", "message": "Username is required"}],
            },
            "missing_password": {
                "code": "VALIDATION_ERROR",
                "message": "Password is required",
                "details": [{"field": "password", "message": "Password is required"}],
            },
            "invalid_email": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid email address",
                "details": [{"field": "email", "message": "Enter a valid email address"}],
            },
            "weak_password": {
                "code": "VALIDATION_ERROR",
                "message": "Password must be at least 8 characters",
                "details": [
                    {
                        "field": "password",
                        "message": "Password must be at least 8 characters",
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

INVALID_CREDENTIALS_RESPONSE = {
    401: openapi_error(
        "Invalid username or password",
        code="INVALID_CREDENTIALS",
        message="Invalid username or password. Please try again.",
    ),
}


@router.post(
    "/login",
    response_model=OrgAdminLoginResponse,
    operation_id="orgAdminLogin",
    summary="Organization admin login",
    description=(
        "Authenticate an organization admin using an email address or username and password.\n\n"
        "**Public endpoint** — no authentication required.\n\n"
        "Accepts `email` and/or `username` (at least one required), `password`, optional "
        "`remember_me`, and optional client `phone` metadata (not persisted).\n\n"
        "Returns **200** with a JWT and dashboard `link` on success.\n\n"
        "Returns **400** when username/email or password is missing, the email format is "
        "invalid, or the password is too short.\n\n"
        "Returns **401** for invalid credentials."
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
async def org_admin_login(
    body: OrgAdminLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> OrgAdminLoginResponse:
    """Authenticate an organization admin and return a JWT access token."""
    result = await org_admin_auth_service.login_org_admin(
        db,
        email=body.email,
        username=body.username,
        password=body.password,
        remember_me=body.remember_me,
    )
    if result is None:
        raise AppException(
            code="INVALID_CREDENTIALS",
            message="Invalid username or password. Please try again.",
            status_code=401,
        )
    return result
