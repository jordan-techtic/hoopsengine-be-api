"""Pydantic schemas for Player module authentication flows."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import UserRole
from app.schemas.profile import ProfileImageResponse

PLAYER_FORGOT_PASSWORD_REQUEST_EXAMPLE = {
    "email": "player@example.com",
    "phone": "+1-555-0100",
}

PLAYER_VERIFY_CODE_REQUEST_EXAMPLE = {
    "email": "player@example.com",
    "verification_code": "123456",
    "phone": "+1-555-0100",
    "password": "StrongPassword123!",
    "confirm_password": "StrongPassword123!",
}

PLAYER_INVITATION_VERIFY_REQUEST_EXAMPLE = {
    "invitation_code": "PC-A1B2C3D4",
    "phone": "+1-555-0100",
}


class PlayerForgotPasswordRequest(BaseModel):
    """Payload for initiating player password recovery via email OTP."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_FORGOT_PASSWORD_REQUEST_EXAMPLE})

    email: str = Field(
        ...,
        min_length=1,
        description="Registered player email address (required)",
        examples=["player@example.com"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the Forgot Password screen (not persisted)",
        examples=["+1-555-0100"],
    )


class PlayerForgotPasswordResponse(BaseModel):
    """Successful player forgot-password response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "A verification code has been sent to your email.",
                "status": "recovery_code_sent",
                "description": "Check your inbox for the 6-digit verification code to reset your password.",
                "link": "http://localhost:5173/player/reset-password",
                "error": None,
                "email": "player@example.com",
            }
        }
    )

    success: bool = Field(default=True, description="Always true when recovery code is sent")
    message: str = Field(description="Human-readable success message for the UI")
    status: str = Field(default="recovery_code_sent", description="Password recovery status")
    description: str | None = Field(
        default=None,
        description="Optional instructions shown below the success message",
    )
    link: str | None = Field(
        default=None,
        description="Next-step URL in the player password recovery flow",
    )
    error: None = Field(default=None, description="Always null on success")
    email: str = Field(description="Email address the verification code was sent to")
    verification_code: str | None = Field(
        default=None,
        description="Debug-only OTP when DEBUG=true",
    )


class PlayerVerifyCodeRequest(BaseModel):
    """
    Payload for player code verification.

    Provide ``invitation_code`` for invitation verification, or ``email`` with
    ``verification_code`` for password recovery OTP verification.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                PLAYER_INVITATION_VERIFY_REQUEST_EXAMPLE,
                PLAYER_VERIFY_CODE_REQUEST_EXAMPLE,
            ]
        }
    )

    invitation_code: str | None = Field(
        default=None,
        description="Player invitation code in PC-XXXXXXXX format (case sensitive)",
        examples=["PC-A1B2C3D4"],
    )
    email: str | None = Field(
        default=None,
        description="Registered player email address used during forgot-password",
        examples=["player@example.com"],
    )
    verification_code: str | None = Field(
        default=None,
        description="6-digit password recovery code sent to the registered email",
        examples=["123456"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata (not persisted)",
        examples=["+1-555-0100"],
    )
    password: str | None = Field(
        default=None,
        description="New password to set after OTP verification (optional on verify-only step)",
        examples=["StrongPassword123!"],
    )
    confirm_password: str | None = Field(
        default=None,
        description="Confirmation of the new password; required when password is provided",
        examples=["StrongPassword123!"],
    )

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip()
        return value


class PlayerVerifyCodeResponse(BaseModel):
    """Successful player recovery code verification response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Verification code confirmed. You can now reset your password.",
                "status": "verified",
                "description": "Enter and confirm your new password to complete the reset.",
                "link": "http://localhost:5173/player/reset-password",
                "error": None,
                "email": "player@example.com",
                "verification_code": None,
                "id": "00000000-0000-4000-8000-000000000003",
                "password": None,
                "reset_token": "abc123resettoken",
            }
        }
    )

    success: bool = Field(default=True, description="Always true on successful verification")
    message: str = Field(description="Human-readable success message for the UI")
    status: str = Field(default="verified", description="Verification status after OTP check")
    description: str | None = Field(
        default=None,
        description="Optional subtitle guiding the user to the next step",
    )
    link: str | None = Field(
        default=None,
        description="URL for the next step in the password recovery flow",
    )
    error: None = Field(default=None, description="Always null on success")
    email: str = Field(description="Verified player email address")
    verification_code: None = Field(
        default=None,
        description="Always null on success (write-only input)",
    )
    id: UUID = Field(description="Player user account identifier")
    password: None = Field(
        default=None,
        description="Always null on success (write-only input)",
    )
    reset_token: str | None = Field(
        default=None,
        description=(
            "Short-lived token issued after verify-only OTP confirmation; "
            "submit to POST /player/reset-password-with-token"
        ),
    )


class PlayerInvitationVerifyResponse(BaseModel):
    """Successful player invitation code verification response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "title": "Player Code Verification",
                "message": "Invitation code verified successfully",
                "status": "verified",
                "description": "Continue registration to link this invitation to your account",
                "link": "http://localhost:5173/player/register",
                "error": None,
                "organization": "Seeded Hoops Club",
                "code": "PC-A1B2C3D4",
                "verification_code": "PC-A1B2C3D4",
                "id": "00000000-0000-4000-8000-000000000037",
                "player_id": "00000000-0000-4000-8000-000000000037",
                "org_id": "00000000-0000-4000-8000-000000000010",
                "player_code": "PC-A1B2C3D4",
            }
        }
    )

    success: bool = Field(default=True, description="Always true on successful verification")
    title: str = Field(default="Player Code Verification", description="Screen title for the UI")
    message: str = Field(description="Human-readable success message for the UI")
    status: str = Field(default="verified", description="Verification status")
    description: str | None = Field(
        default=None,
        description="Optional subtitle guiding the user to the next step",
    )
    link: str | None = Field(
        default=None,
        description="URL for the next step in player registration",
    )
    error: None = Field(default=None, description="Always null on success")
    organization: str | None = Field(
        default=None,
        description="Organization name associated with the invitation",
    )
    code: str = Field(description="Verified invitation code value")
    verification_code: str = Field(description="Verified invitation code (alias for code)")
    id: UUID = Field(description="Client player record identifier")
    player_id: UUID = Field(description="Client player record identifier")
    org_id: UUID | None = Field(default=None, description="Organization identifier for the player")
    player_code: str = Field(description="Verified player invitation code")


PLAYER_LOGIN_REQUEST_EXAMPLE = {
    "email": "player@example.com",
    "password": "StrongPassword123!",
    "remember_me": False,
    "phone": "+1-555-0100",
}


class PlayerUserPublic(BaseModel):
    """Player profile fields returned after login."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    username: str | None = None
    role: UserRole
    org_id: UUID | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_super_admin: bool
    is_active: bool
    last_sign_in_at: datetime | None = None


class PlayerLoginRequest(BaseModel):
    """Payload for player login with email or username."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_LOGIN_REQUEST_EXAMPLE})

    email: str = Field(
        ...,
        min_length=1,
        description="Player email address or username (required)",
        examples=["player@example.com", "playeruser"],
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Account password (required)",
        examples=["StrongPassword123!"],
    )
    remember_me: bool = Field(
        default=False,
        description="When true, issue a longer-lived JWT for extended sessions",
        examples=[False],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the login screen (not persisted)",
        examples=["+1-555-0100"],
    )


class PlayerLoginResponse(BaseModel):
    """Successful player login response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "title": "LOGIN",
                "message": "Login successful",
                "status": "authenticated",
                "description": "Welcome back to Hoops Engine",
                "link": "http://localhost:5173/player/dashboard",
                "error": None,
                "email": "player@example.com",
                "username": "playeruser",
                "id": "00000000-0000-4000-8000-000000000003",
                "password": None,
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in_hours": 24,
                "remember_me": False,
                "user": {
                    "id": "00000000-0000-4000-8000-000000000003",
                    "email": "player@example.com",
                    "username": "playeruser",
                    "role": "player",
                    "is_super_admin": False,
                    "is_active": True,
                },
            }
        }
    )

    success: bool = Field(default=True, description="Always true on successful login")
    title: str = Field(default="LOGIN", description="Screen title for the login UI")
    message: str = Field(description="Human-readable success message for the UI")
    status: str = Field(default="authenticated", description="Login status after success")
    description: str | None = Field(
        default=None,
        description="Optional subtitle shown after login",
    )
    link: str | None = Field(
        default=None,
        description="Navigation target after successful login",
    )
    error: None = Field(default=None, description="Always null on success")
    email: str = Field(description="Authenticated player email address")
    username: str | None = Field(default=None, description="Authenticated player username")
    id: UUID = Field(description="Authenticated player user identifier")
    password: None = Field(
        default=None,
        description="Always null on success (write-only input)",
    )
    access_token: str = Field(description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type for Authorization header")
    expires_in_hours: int = Field(description="JWT validity in hours")
    remember_me: bool = Field(description="Whether an extended session token was issued")
    user: PlayerUserPublic = Field(description="Authenticated player profile")


class PlayerLoginValidateResponse(BaseModel):
    """Response for pre-submit login field validation."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "title": "LOGIN",
                "valid": True,
                "message": "Login fields look good",
                "status": "valid",
                "description": "You can submit the login form",
                "errors": None,
                "error": None,
                "email": "player@example.com",
                "id": "00000000-0000-4000-8000-000000000003",
                "username": "playeruser",
                "name": "Player User",
                "first_name": "Player",
                "last_name": "User",
                "phone": "+1 (555) 382-9102",
                "phone_number": "+1 (555) 382-9102",
                "address": None,
                "avatar": None,
            }
        }
    )

    success: bool = Field(default=True, description="Always true for validate responses")
    title: str = Field(default="LOGIN", description="Screen title for the login UI")
    valid: bool = Field(description="True when email/username and password pass validation")
    message: str = Field(description="Human-readable validation summary")
    status: str = Field(description="Validation status (`valid` or `invalid`)")
    description: str | None = Field(
        default=None,
        description="Optional guidance for the login form",
    )
    errors: list[dict[str, str]] | None = Field(
        default=None,
        description="Field-level validation errors when valid is false",
    )
    error: None = Field(default=None, description="Always null on validate responses")
    email: str | None = Field(
        default=None,
        description="Submitted email/username or matched player email for form state",
    )
    id: UUID | None = Field(
        default=None,
        description="Matched player user identifier when the identifier resolves to an account",
    )
    username: str | None = Field(default=None, description="Matched player username")
    name: str | None = Field(default=None, description="Matched player display name")
    first_name: str | None = Field(default=None, description="Matched player first name")
    last_name: str | None = Field(default=None, description="Matched player last name")
    phone: str | None = Field(
        default=None,
        description="Matched player phone for mobile form echo",
    )
    phone_number: str | None = Field(
        default=None,
        description="Matched player phone number for mobile form echo",
    )
    address: str | None = Field(
        default=None,
        description="Optional address placeholder for frontend form state",
    )
    avatar: ProfileImageResponse | None = Field(
        default=None,
        description="Matched player avatar metadata when available",
    )



PLAYER_RESET_PASSWORD_WITH_TOKEN_REQUEST_EXAMPLE = {
    "reset_token": "abc123resettoken",
    "new_password": "StrongPassword123!",
    "confirm_password": "StrongPassword123!",
    "phone": "+1-555-0100",
}


class PlayerResetPasswordWithTokenRequest(BaseModel):
    """Payload for resetting a player password after OTP verification (no JWT)."""

    model_config = ConfigDict(
        json_schema_extra={"example": PLAYER_RESET_PASSWORD_WITH_TOKEN_REQUEST_EXAMPLE}
    )

    reset_token: str = Field(
        ...,
        min_length=1,
        description="Short-lived reset token returned from verify-code (verify-only step)",
        examples=["abc123resettoken"],
    )
    new_password: str = Field(
        ...,
        description=(
            "New account password (minimum 8 characters with uppercase, lowercase, "
            "number, and special character)"
        ),
        examples=["StrongPassword123!"],
    )
    confirm_password: str = Field(
        ...,
        description="Confirmation of the new password; must match new_password",
        examples=["StrongPassword123!"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )
    password: str | None = Field(
        default=None,
        description="Optional Password Strength UI echo (not used for reset)",
        examples=["StrongPassword123!"],
    )


PLAYER_RESET_PASSWORD_REQUEST_EXAMPLE = {
    "new_password": "StrongPassword123!",
    "confirm_password": "StrongPassword123!",
    "phone": "+1-555-0100",
    "password": "StrongPassword123!",
}


class PlayerResetPasswordRequest(BaseModel):
    """Payload for resetting the authenticated player's password."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_RESET_PASSWORD_REQUEST_EXAMPLE})

    new_password: str = Field(
        ...,
        description=(
            "New account password (minimum 8 characters with uppercase, lowercase, "
            "number, and special character)"
        ),
        examples=["StrongPassword123!"],
    )
    confirm_password: str = Field(
        ...,
        description="Confirmation of the new password; must match new_password",
        examples=["StrongPassword123!"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )
    password: str | None = Field(
        default=None,
        description=(
            "Optional echo of the Password Strength field from the Reset Password UI "
            "(not used for reset; use new_password)"
        ),
        examples=["StrongPassword123!"],
    )


class PlayerResetPasswordResponse(BaseModel):
    """Successful authenticated player password reset response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Password has been reset successfully.",
                "status": "password_reset",
                "description": "Your new password is now active. Use it the next time you sign in.",
                "link": "http://localhost:5173/player/login",
                "error": None,
                "id": "00000000-0000-4000-8000-000000000003",
                "password": None,
            }
        }
    )

    success: bool = Field(default=True, description="Always true on successful password reset")
    message: str = Field(description="Human-readable success message for the UI")
    status: str = Field(default="password_reset", description="Outcome status after reset")
    description: str | None = Field(
        default=None,
        description="Instructional text about the completed password reset",
    )
    link: str | None = Field(
        default=None,
        description="Navigation target after successful reset (e.g. player login screen)",
    )
    error: None = Field(default=None, description="Always null on success")
    id: UUID = Field(description="Player user UUID whose password was reset")
    password: None = Field(default=None, description="Always null on success (password is write-only)")
