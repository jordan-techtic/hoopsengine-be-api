"""Pydantic schemas for organization admin reset password APIs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

ORG_ADMIN_RESET_PASSWORD_REQUEST_EXAMPLE = {
    "new_password": "StrongPassword123!",
    "confirm_password": "StrongPassword123!",
    "phone": "+1-555-0100",
}


class OrgAdminResetPasswordRequest(BaseModel):
    """Payload for POST /admin/reset-password."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_RESET_PASSWORD_REQUEST_EXAMPLE})

    new_password: str = Field(
        description="New account password (minimum 8 characters with uppercase, number, and special character)",
        examples=["StrongPassword123!"],
    )
    confirm_password: str = Field(
        description="Confirmation of the new password; must match new_password",
        examples=["StrongPassword123!"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional phone metadata from the status bar (not persisted unless non-empty)",
        examples=["+1-555-0100"],
    )
