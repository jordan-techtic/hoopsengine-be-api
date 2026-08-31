"""Request and response schemas for player change password."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin

PLAYER_CHANGE_PASSWORD_EXAMPLE = {
    "current_password": "StrongPassword123!",
    "new_password": "NewSecure456!",
    "confirm_new_password": "NewSecure456!",
    "phone": "+1-555-0100",
    "password": "NewSecure456!",
}


class PlayerChangePasswordRequest(BaseModel):
    """Payload for POST /api/v1/player/change-password."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_CHANGE_PASSWORD_EXAMPLE})

    current_password: str = Field(
        ...,
        description="Current account password for verification",
        examples=["StrongPassword123!"],
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description=(
            "New password meeting strength requirements (minimum 8 characters with "
            "uppercase, lowercase, number, and special character)"
        ),
        examples=["NewSecure456!"],
    )
    confirm_new_password: str | None = Field(
        default=None,
        description="Confirmation of the new password; must match new_password",
        examples=["NewSecure456!"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )
    password: str | None = Field(
        default=None,
        description="Figma write-only alias for confirm_new_password from the Confirm New Password field",
        examples=["NewSecure456!"],
    )

    @model_validator(mode="after")
    def map_password_alias(self) -> Self:
        if self.confirm_new_password is None and self.password is not None:
            object.__setattr__(self, "confirm_new_password", self.password)
        return self


class PlayerChangePasswordResponse(MobileWriteOnlyPasswordMixin):
    """Successful player change-password response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Password changed successfully",
                "status": "password_changed",
                "description": "Your new password is now active",
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "password": None,
                "phone": "+1-555-0100",
            }
        }
    )

    success: bool = Field(default=True, description="Always true on successful password change")
    message: str = Field(description="Human-readable success message for the UI")
    status: str = Field(default="password_changed", description="Outcome status after password change")
    description: str | None = Field(
        default=None,
        description="Instructional text confirming the password update",
    )
    link: str | None = Field(default=None, description="Optional navigation target after success")
    error: None = Field(default=None, description="Always null on success")
    id: UUID = Field(description="Player user UUID")
    phone: str | None = Field(
        default=None,
        description="Optional phone metadata echoed from the request",
    )
