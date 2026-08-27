from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import UserRole

REGISTER_REQUEST_EXAMPLE = {
    "first_name": "John",
    "last_name": "Doe",
    "username": "johndoe",
    "email": "john.doe@example.com",
    "password": "StrongPassword123!",
    "confirm_password": "StrongPassword123!",
    "terms_accepted": True,
    "phone": "+1-555-0100",
}


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: UserRole
    org_id: UUID | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_super_admin: bool
    is_active: bool
    last_sign_in_at: datetime | None = None


class CoachUserPublic(UserPublic):
    """Coach profile fields returned after login."""

    username: str | None = None


COACH_LOGIN_REQUEST_EXAMPLE = {
    "email": "john.doe@example.com",
    "password": "StrongPassword123!",
    "remember_me": False,
    "phone": "+1-555-0100",
}

COACH_FORGOT_PASSWORD_REQUEST_EXAMPLE = {
    "email": "john.doe@example.com",
    "phone": "+1-555-0100",
}


class CoachLoginRequest(BaseModel):
    """Payload for coach login with email or username."""

    model_config = ConfigDict(json_schema_extra={"example": COACH_LOGIN_REQUEST_EXAMPLE})

    email: str | None = Field(
        default=None,
        description="Coach email address or username",
        examples=["john.doe@example.com"],
    )
    password: str | None = Field(
        default=None,
        description="Account password",
        examples=["StrongPassword123!"],
    )
    remember_me: bool = Field(
        default=False,
        description="When true, issue a longer-lived JWT for extended sessions",
        examples=[False],
    )
    phone: str | None = Field(
        default=None,
        description="Optional phone metadata from the login screen",
        examples=["+1-555-0100"],
    )


class CoachLoginResponse(BaseModel):
    """Successful coach login response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Login successful",
                "status": "authenticated",
                "description": "Welcome back to Hoops Engine",
                "link": "/coach/dashboard",
                "error": None,
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in_hours": 24,
                "remember_me": False,
                "user": {
                    "id": "11111111-2222-3333-4444-555555555555",
                    "email": "john.doe@example.com",
                    "username": "johndoe",
                    "role": "coach",
                    "is_super_admin": False,
                    "is_active": True,
                },
            }
        }
    )

    success: bool = Field(default=True, description="Always true on successful login")
    message: str = Field(description="Human-readable success message for the UI")
    status: str = Field(default="authenticated", description="Login status after success")
    description: str | None = Field(
        default=None,
        description="Optional subtitle shown after login",
    )
    link: str | None = Field(
        default=None,
        description="Optional navigation target after login",
    )
    error: None = Field(default=None, description="Always null on success")
    access_token: str = Field(description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type for Authorization header")
    expires_in_hours: int = Field(description="JWT validity in hours")
    remember_me: bool = Field(description="Whether an extended session token was issued")
    user: CoachUserPublic = Field(description="Authenticated coach profile")


class CoachForgotPasswordRequest(BaseModel):
    """Payload for initiating coach password recovery."""

    model_config = ConfigDict(json_schema_extra={"example": COACH_FORGOT_PASSWORD_REQUEST_EXAMPLE})

    email: EmailStr = Field(
        ...,
        description="Registered coach email address",
        examples=["john.doe@example.com"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional phone metadata from the login screen",
        examples=["+1-555-0100"],
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class CoachForgotPasswordResponse(BaseModel):
    """Successful coach forgot-password response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Password reset link has been sent to your email.",
                "status": "reset_email_sent",
                "description": "Check your inbox for instructions to reset your password.",
                "link": "http://localhost:5173/reset-password",
                "error": None,
            }
        }
    )

    success: bool = Field(default=True, description="Always true when reset email is sent")
    message: str = Field(description="Human-readable success message for the UI")
    status: str = Field(default="reset_email_sent", description="Password recovery status")
    description: str | None = Field(
        default=None,
        description="Optional instructions for the user",
    )
    link: str | None = Field(
        default=None,
        description="Password reset page URL for the Forgot Password flow",
    )
    error: None = Field(default=None, description="Always null on success")
    reset_token: str | None = Field(
        default=None,
        description="Debug-only reset token when DEBUG=true",
    )


class LoginRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "admin.hoopsengine@yopmail.com",
                "password": "Admin@123",
            }
        }
    )

    email: EmailStr
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int
    user: UserPublic


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"email": "admin.hoopsengine@yopmail.com"},
        }
    )

    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str
    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=72)


class ValidateResetTokenRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "token": "A7ms2FsT-sGzC4HjcdIRQoacF7sHvlWIAIG7vLK_0b0",
            }
        }
    )

    token: str = Field(min_length=1)


class ValidateResetTokenResponse(BaseModel):
    valid: bool
    message: str
    email: EmailStr | None = None


class MessageResponse(BaseModel):
    message: str


class RegisterRequest(BaseModel):
    """Payload for coach self-registration on the Register screen."""

    model_config = ConfigDict(json_schema_extra={"example": REGISTER_REQUEST_EXAMPLE})

    first_name: str = Field(
        ...,
        description="Coach first name (required, max 50 characters)",
        examples=["John"],
    )
    last_name: str = Field(
        ...,
        description="Coach last name (required, max 50 characters)",
        examples=["Doe"],
    )
    username: str = Field(
        ...,
        description="Unique username (required, max 30 characters, letters/numbers/underscore)",
        examples=["johndoe"],
    )
    email: EmailStr = Field(
        ...,
        description="Login email address (required, must be unique)",
        examples=["john.doe@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description=(
            "Account password (min 8 chars with uppercase, lowercase, number, and special character)"
        ),
        examples=["StrongPassword123!"],
    )
    confirm_password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description="Must match password exactly",
        examples=["StrongPassword123!"],
    )
    terms_accepted: bool = Field(
        ...,
        description="Must be true to complete registration",
        examples=[True],
    )
    phone: str | None = Field(
        default=None,
        description="Optional phone number from the registration form",
        examples=["+1-555-0100"],
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class RegisterResponse(BaseModel):
    """Successful coach registration response for the Register screen."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Registration successful. Please verify your email.",
                "status": "pending_verification",
                "description": "A 6-digit verification code was sent to your email.",
                "link": "/verify-email",
                "error": None,
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in_hours": 24,
                "id": "11111111-2222-3333-4444-555555555555",
                "first_name": "John",
                "last_name": "Doe",
                "name": "John Doe",
                "username": "johndoe",
                "email": "john.doe@example.com",
                "address": None,
            }
        }
    )

    success: bool = Field(default=True, description="Always true on successful registration")
    message: str = Field(description="Human-readable success message for the UI")
    status: str = Field(
        default="pending_verification",
        description="Registration status until email is verified",
    )
    description: str | None = Field(
        default=None,
        description="Optional subtitle shown under the success message",
    )
    link: str | None = Field(
        default=None,
        description="Optional in-app navigation target after registration",
    )
    error: None = Field(default=None, description="Always null on success")
    access_token: str = Field(description="JWT for the email verification screen")
    token_type: str = Field(default="bearer", description="Token type for Authorization header")
    expires_in_hours: int = Field(description="JWT validity in hours")
    id: UUID = Field(description="New coach user UUID")
    first_name: str = Field(description="Registered first name")
    last_name: str = Field(description="Registered last name")
    name: str = Field(description="Display name derived from first and last name")
    username: str = Field(description="Registered username")
    email: EmailStr = Field(description="Registered email address")
    address: str | None = Field(
        default=None,
        description="Optional address (not collected at registration)",
    )


VERIFY_EMAIL_REQUEST_EXAMPLE = {
    "email": "john.doe@example.com",
    "otp_code": "123456",
    "phone": "+1-555-0100",
}

RESEND_VERIFICATION_REQUEST_EXAMPLE = {
    "email": "john.doe@example.com",
    "phone": "+1-555-0100",
}


class VerifyEmailRequest(BaseModel):
    """Payload for verifying a coach email with a 6-digit OTP code."""

    model_config = ConfigDict(json_schema_extra={"example": VERIFY_EMAIL_REQUEST_EXAMPLE})

    otp_code: str | None = Field(
        default=None,
        description="Six-digit verification code sent to the user's email",
        examples=["123456"],
    )
    email: EmailStr | None = Field(
        default=None,
        description="Registered email address (defaults to the authenticated user's email)",
        examples=["john.doe@example.com"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional phone metadata from the verification screen",
        examples=["+1-555-0100"],
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            cleaned = value.strip().lower()
            return cleaned or None
        return value


class ResendVerificationCodeRequest(BaseModel):
    """Payload for requesting a new email verification OTP."""

    model_config = ConfigDict(json_schema_extra={"example": RESEND_VERIFICATION_REQUEST_EXAMPLE})

    email: EmailStr | None = Field(
        default=None,
        description="Registered email address (defaults to the authenticated user's email)",
        examples=["john.doe@example.com"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional phone metadata from the verification screen",
        examples=["+1-555-0100"],
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            cleaned = value.strip().lower()
            return cleaned or None
        return value


class VerifyEmailResponse(BaseModel):
    """Successful email verification response for the verification screen."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Email verified successfully.",
                "status": "verified",
                "description": "Your email address has been confirmed.",
                "link": "/coach/dashboard",
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "email": "john.doe@example.com",
                "code": None,
                "otp": None,
                "address": None,
            }
        }
    )

    success: bool = Field(default=True, description="Always true on successful verification")
    message: str = Field(description="Human-readable success message for the UI")
    status: str = Field(default="verified", description="Verification status after success")
    description: str | None = Field(
        default=None,
        description="Optional subtitle shown under the success message",
    )
    link: str | None = Field(
        default=None,
        description="Optional navigation target after successful verification",
    )
    error: None = Field(default=None, description="Always null on success")
    id: UUID = Field(description="Verified user UUID")
    email: EmailStr = Field(description="Verified email address")
    code: None = Field(default=None, description="Always null on success (OTP is write-only)")
    otp: None = Field(default=None, description="Always null on success (OTP is write-only)")
    address: str | None = Field(default=None, description="Optional address (not collected here)")


class ResendVerificationCodeResponse(BaseModel):
    """Successful resend verification code response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "A new verification code has been sent to your email.",
                "status": "pending_verification",
                "description": "We sent a 6-digit code to john.doe@example.com",
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "email": "john.doe@example.com",
                "code": None,
                "otp": None,
                "address": None,
            }
        }
    )

    success: bool = Field(default=True, description="Always true when resend succeeds")
    message: str = Field(description="Human-readable success message for the UI")
    status: str = Field(
        default="pending_verification",
        description="Verification status while email confirmation is pending",
    )
    description: str | None = Field(
        default=None,
        description="Optional subtitle describing where the code was sent",
    )
    link: str | None = Field(default=None, description="Optional navigation target")
    error: None = Field(default=None, description="Always null on success")
    id: UUID = Field(description="User UUID")
    email: EmailStr = Field(description="Email address the code was sent to")
    code: None = Field(default=None, description="Always null on success (OTP is write-only)")
    otp: None = Field(default=None, description="Always null on success (OTP is write-only)")
    address: str | None = Field(default=None, description="Optional address (not collected here)")


CANCEL_VERIFICATION_REQUEST_EXAMPLE = {
    "cancel_verification": True,
    "phone": "+1-555-0100",
}


class CancelVerificationRequest(BaseModel):
    """Payload confirming cancellation of the pending verification signup flow."""

    model_config = ConfigDict(json_schema_extra={"example": CANCEL_VERIFICATION_REQUEST_EXAMPLE})

    cancel_verification: bool | None = Field(
        default=None,
        description="Must be true to confirm cancellation of verification and signup",
        examples=[True],
    )
    phone: str | None = Field(
        default=None,
        description="Optional phone metadata from the status bar",
        examples=["+1-555-0100"],
    )

    @field_validator("cancel_verification", mode="before")
    @classmethod
    def coerce_cancel_flag(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized == "true":
                return True
            if normalized == "false":
                return False
        return value


class CancelVerificationResponse(BaseModel):
    """Successful cancel verification response for the Cancel Verification screen."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Verification cancelled successfully.",
                "status": "cancelled",
                "description": "Your signup has been cancelled. Verification progress has been lost.",
                "link": "http://localhost:3000/register",
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
            }
        }
    )

    success: bool = Field(default=True, description="Always true on successful cancellation")
    message: str = Field(description="Human-readable success message for the UI")
    status: str = Field(default="cancelled", description="Verification status after cancellation")
    description: str | None = Field(
        default=None,
        description="Instructional text explaining the result of cancellation",
    )
    link: str | None = Field(
        default=None,
        description="Navigation target after cancellation (e.g. back to registration)",
    )
    error: None = Field(default=None, description="Always null on success")
    id: UUID = Field(description="Cancelled user UUID")


class ContinueVerificationResponse(BaseModel):
    """Successful continue verification response for the Cancel Verification screen."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Continue with email verification.",
                "status": "pending_verification",
                "description": "Enter the 6-digit verification code sent to your email.",
                "link": "http://localhost:3000/verify-email",
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "email": "john.doe@example.com",
                "phone": "+1-555-0100",
            }
        }
    )

    success: bool = Field(default=True, description="Always true when verification can continue")
    message: str = Field(description="Human-readable success message for the UI")
    status: str = Field(
        default="pending_verification",
        description="Verification status while email confirmation is pending",
    )
    description: str | None = Field(
        default=None,
        description="Instructional text for continuing verification",
    )
    link: str | None = Field(
        default=None,
        description="Navigation target for the verification screen",
    )
    error: None = Field(default=None, description="Always null on success")
    id: UUID = Field(description="User UUID")
    email: EmailStr = Field(description="Email address awaiting verification")
    phone: str | None = Field(
        default=None,
        description="Optional phone metadata echoed from the status bar query parameter",
    )


RESET_PASSWORD_FORM_REQUEST_EXAMPLE = {
    "new_password": "StrongPassword123!",
    "confirm_password": "StrongPassword123!",
    "phone": "+1-555-0100",
}


class PasswordStrengthRequirements(BaseModel):
    """Checklist of password strength requirements for the Reset Password UI."""

    min_length: bool = Field(description="At least 8 characters")
    has_number: bool = Field(description="At least one number")
    has_special: bool = Field(description="At least one special character")
    has_uppercase: bool = Field(description="At least one uppercase letter")
    has_lowercase: bool = Field(description="At least one lowercase letter")


class ResetPasswordFormRequest(BaseModel):
    """Payload for resetting the authenticated user's password."""

    model_config = ConfigDict(json_schema_extra={"example": RESET_PASSWORD_FORM_REQUEST_EXAMPLE})

    new_password: str | None = Field(
        default=None,
        description="New account password (minimum 8 characters with number and special character)",
        examples=["StrongPassword123!"],
    )
    confirm_password: str | None = Field(
        default=None,
        description="Confirmation of the new password; must match new_password",
        examples=["StrongPassword123!"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional phone metadata from the status bar",
        examples=["+1-555-0100"],
    )


class ResetPasswordFormResponse(BaseModel):
    """Successful authenticated password reset response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Password has been reset successfully.",
                "status": "password_reset",
                "description": "Your new password is now active. Use it the next time you sign in.",
                "link": "http://localhost:3000/coach/login",
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
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
        description="Navigation target after successful reset (e.g. login screen)",
    )
    error: None = Field(default=None, description="Always null on success")
    id: UUID = Field(description="User UUID whose password was reset")
    password: None = Field(default=None, description="Always null on success (password is write-only)")


class ValidatePasswordStrengthResponse(BaseModel):
    """Password strength evaluation for the Reset Password strength indicator."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Password meets all strength requirements.",
                "status": "valid",
                "description": "Password strength requirements for a secure account.",
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "password": None,
                "strength": "strong",
                "requirements": {
                    "min_length": True,
                    "has_number": True,
                    "has_special": True,
                    "has_uppercase": True,
                    "has_lowercase": True,
                },
                "phone": "+1-555-0100",
            }
        }
    )

    success: bool = Field(default=True, description="Always true when validation completes")
    message: str = Field(description="Human-readable validation summary for the UI")
    status: str = Field(description="Validation outcome: valid or invalid")
    description: str | None = Field(
        default=None,
        description="Instructional text about password requirements",
    )
    link: str | None = Field(default=None, description="Optional navigation target")
    error: None = Field(default=None, description="Always null on success")
    id: UUID = Field(description="Authenticated user UUID")
    password: None = Field(default=None, description="Always null (password is write-only)")
    strength: str = Field(description="Overall strength label: weak, medium, or strong")
    requirements: PasswordStrengthRequirements = Field(
        description="Checklist of individual password requirements",
    )
    phone: str | None = Field(
        default=None,
        description="Optional phone metadata echoed from the status bar query parameter",
    )


RESET_PASSWORD_FORM_REQUEST_EXAMPLE = {
    "new_password": "StrongPassword123!",
    "confirm_password": "StrongPassword123!",
    "phone": "+1-555-0100",
}


class PasswordStrengthRequirements(BaseModel):
    """Checklist of password strength requirements for the Reset Password UI."""

    min_length: bool = Field(description="At least 8 characters")
    has_number: bool = Field(description="At least one number")
    has_special: bool = Field(description="At least one special character")
    has_uppercase: bool = Field(description="At least one uppercase letter")
    has_lowercase: bool = Field(description="At least one lowercase letter")


class ResetPasswordFormRequest(BaseModel):
    """Payload for resetting the authenticated user's password."""

    model_config = ConfigDict(json_schema_extra={"example": RESET_PASSWORD_FORM_REQUEST_EXAMPLE})

    new_password: str | None = Field(
        default=None,
        description="New account password (minimum 8 characters with number and special character)",
        examples=["StrongPassword123!"],
    )
    confirm_password: str | None = Field(
        default=None,
        description="Confirmation of the new password; must match new_password",
        examples=["StrongPassword123!"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional phone metadata from the status bar",
        examples=["+1-555-0100"],
    )


class ResetPasswordFormResponse(BaseModel):
    """Successful authenticated password reset response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Password has been reset successfully.",
                "status": "password_reset",
                "description": "Your new password is now active. Use it the next time you sign in.",
                "link": "http://localhost:3000/coach/login",
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
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
        description="Navigation target after successful reset (e.g. login screen)",
    )
    error: None = Field(default=None, description="Always null on success")
    id: UUID = Field(description="User UUID whose password was reset")
    password: None = Field(default=None, description="Always null on success (password is write-only)")


class ValidatePasswordStrengthResponse(BaseModel):
    """Password strength evaluation for the Reset Password strength indicator."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Password meets all strength requirements.",
                "status": "valid",
                "description": "Password strength requirements for a secure account.",
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "password": None,
                "strength": "strong",
                "requirements": {
                    "min_length": True,
                    "has_number": True,
                    "has_special": True,
                    "has_uppercase": True,
                    "has_lowercase": True,
                },
                "phone": "+1-555-0100",
            }
        }
    )

    success: bool = Field(default=True, description="Always true when validation completes")
    message: str = Field(description="Human-readable validation summary for the UI")
    status: str = Field(description="Validation outcome: valid or invalid")
    description: str | None = Field(
        default=None,
        description="Instructional text about password requirements",
    )
    link: str | None = Field(default=None, description="Optional navigation target")
    error: None = Field(default=None, description="Always null on success")
    id: UUID = Field(description="Authenticated user UUID")
    password: None = Field(default=None, description="Always null (password is write-only)")
    strength: str = Field(description="Overall strength label: weak, medium, or strong")
    requirements: PasswordStrengthRequirements = Field(
        description="Checklist of individual password requirements",
    )
    phone: str | None = Field(
        default=None,
        description="Optional phone metadata echoed from the status bar query parameter",
    )
