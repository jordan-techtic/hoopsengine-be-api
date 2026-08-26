from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


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
