"""Pydantic schemas for the Role Selection onboarding screen."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import RoleOption

ROLE_SELECTION_SUBMIT_EXAMPLE = {
    "selected_role": "Coach",
    "phone": "+1-555-0100",
}


class RoleSelectionSubmitRequest(BaseModel):
    """Payload for POST /role-selection when the user taps Continue."""

    model_config = ConfigDict(json_schema_extra={"example": ROLE_SELECTION_SUBMIT_EXAMPLE})

    selected_role: str = Field(
        ...,
        description="UI role label or stored value: Coach, Player, or Organiser",
        examples=["Coach"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )
    session_token: UUID | None = Field(
        default=None,
        description="Existing selection session token when updating a prior choice",
        examples=["11111111-2222-3333-4444-555555555555"],
    )


class RoleSelectionSubmitResponse(BaseModel):
    """Successful role selection response for the mobile client."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Role selected successfully",
                "status": "ready",
                "description": "Continue to registration to create your account",
                "title": "Select Your Role",
                "link": "http://localhost:5173/register",
                "error": None,
                "session_token": "11111111-2222-3333-4444-555555555555",
                "selected_role": "coach",
                "role": "coach",
                "id": "11111111-2222-3333-4444-555555555555",
            }
        }
    )

    success: bool = Field(default=True, description="Always true on success")
    message: str = Field(description="Human-readable success message for the UI")
    status: str = Field(default="ready", description="Screen state indicator")
    description: str | None = Field(
        default=None,
        description="Subtitle guiding the user to the next onboarding step",
    )
    title: str = Field(default="Select Your Role", description="Screen title for the mobile client")
    link: str | None = Field(
        default=None,
        description="Navigation target for the next onboarding step (registration)",
    )
    error: None = Field(default=None, description="Always null on success")
    session_token: UUID = Field(description="Opaque token identifying this role selection session")
    selected_role: str = Field(description="Stored role value (coach, player, org_admin)")
    role: str = Field(description="Same as selected_role — bound for mobile form state")
    id: UUID = Field(description="Role selection record UUID")


class RoleCatalogResponse(BaseModel):
    """Available roles for the Role Selection screen."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Roles loaded successfully",
                "status": "ready",
                "description": "Choose how you will use Hoops Engine",
                "title": "Select Your Role",
                "link": None,
                "error": None,
                "id": None,
                "role": None,
                "image": None,
                "phone": None,
                "phone_number": None,
                "email": None,
                "name": None,
                "first_name": None,
                "last_name": None,
                "address": None,
                "code": None,
                "roles": [
                    {
                        "value": "coach",
                        "label": "Coach",
                        "description": "Manage teams, practices, and player development",
                    }
                ],
            }
        }
    )

    success: bool = Field(default=True, description="Always true on success")
    message: str = Field(description="Human-readable status message for the UI")
    status: str = Field(default="ready", description="Screen state indicator")
    description: str | None = Field(default=None, description="Subtitle shown under the screen title")
    title: str = Field(default="Select Your Role", description="Screen title for the mobile client")
    link: str | None = Field(default=None, description="Optional navigation target")
    error: None = Field(default=None, description="Always null on success")
    id: UUID | None = Field(default=None, description="Role selection record UUID when a session exists")
    role: str | None = Field(default=None, description="Selected role value when a session exists")
    image: str | None = Field(default=None, description="Optional hero image URL for the screen")
    phone: str | None = Field(default=None, description="Optional client metadata from the status bar")
    phone_number: str | None = Field(default=None, description="Optional contact phone placeholder for the form")
    email: str | None = Field(default=None, description="Optional contact email placeholder for the form")
    name: str | None = Field(default=None, description="Optional display name placeholder for the form")
    first_name: str | None = Field(default=None, description="Optional first name placeholder for the form")
    last_name: str | None = Field(default=None, description="Optional last name placeholder for the form")
    address: str | None = Field(default=None, description="Optional address placeholder for the form")
    code: str | None = Field(default=None, description="Optional player code placeholder for the form")
    roles: list[RoleOption] = Field(description="Selectable roles for the role cards")


class RoleSelectionCurrentResponse(BaseModel):
    """Current role selection for a session token."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Role selection loaded",
                "status": "ready",
                "description": "Your selected role",
                "title": "Select Your Role",
                "link": None,
                "error": None,
                "session_token": "11111111-2222-3333-4444-555555555555",
                "selected_role": "coach",
                "role": "coach",
                "id": "11111111-2222-3333-4444-555555555555",
            }
        }
    )

    success: bool = Field(default=True, description="Always true on success")
    message: str = Field(description="Human-readable status message for the UI")
    status: str = Field(default="ready", description="Screen state indicator")
    description: str | None = Field(default=None, description="Subtitle describing the saved selection")
    title: str = Field(default="Select Your Role", description="Screen title for the mobile client")
    link: str | None = Field(default=None, description="Optional navigation target")
    error: None = Field(default=None, description="Always null on success")
    session_token: UUID = Field(description="Role selection session token")
    selected_role: str = Field(description="Stored role value (coach, player, org_admin)")
    role: str = Field(description="Same as selected_role — bound for mobile form state")
    id: UUID = Field(description="Role selection record UUID")
