"""Pydantic schemas for coach Remove Player APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

REMOVAL_CONFIRMATION_MESSAGE = (
    "Are you sure you want to delete this coach? This action is permanent."
)

PLAYER_REMOVAL_REQUEST_EXAMPLE = {
    "full_name": "Jane Doe",
    "email": "sarah.jenkins@school.edu",
    "phone": "(555) 123-4567",
}


class PlayerRemovalRequest(BaseModel):
    """Payload for POST /coach/remove_player."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_REMOVAL_REQUEST_EXAMPLE})

    full_name: str = Field(
        description="Player full name shown on the Remove Player confirmation form",
        examples=["Jane Doe"],
    )
    email: str = Field(
        description="Player contact email used to identify the roster record",
        examples=["sarah.jenkins@school.edu"],
    )
    phone: str = Field(
        description="Player contact phone number used to confirm removal",
        examples=["(555) 123-4567"],
    )


class PlayerRemovalConfirmResponse(BaseModel):
    """Confirmation copy for the Remove Player modal."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Confirm player removal",
                "status": "confirm",
                "description": REMOVAL_CONFIRMATION_MESSAGE,
                "title": "Remove Player",
                "link": None,
                "error": None,
                "confirmation_message": REMOVAL_CONFIRMATION_MESSAGE,
                "can_remove": False,
                "name": None,
                "email": None,
                "phone": None,
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="confirm")
    description: str
    title: str = Field(default="Remove Player")
    link: str | None = None
    error: None = None
    confirmation_message: str = Field(
        description="Exact copy shown in the permanent deletion confirmation modal",
    )
    can_remove: bool = Field(
        default=False,
        description=(
            "True when optional preview query fields (full_name, email, phone) "
            "are all present and valid so the Remove Player button may be enabled"
        ),
    )
    name: str | None = Field(default=None, description="Echo of full_name when provided")
    email: str | None = Field(default=None, description="Echo of email when provided")
    phone: str | None = Field(default=None, description="Echo of phone when provided")


class PlayerRemovalResponse(BaseModel):
    """Successful player removal response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Player removed successfully",
                "status": "removed",
                "description": "The player was removed from the roster",
                "title": "Remove Player",
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "player_id": "11111111-2222-3333-4444-555555555555",
                "name": "Jane Doe",
                "full_name": "Jane Doe",
                "email": "sarah.jenkins@school.edu",
                "phone": "5551234567",
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="removed")
    description: str | None = None
    title: str = Field(default="Remove Player")
    link: str | None = None
    error: None = None
    id: UUID
    player_id: UUID
    name: str
    full_name: str
    email: str
    phone: str
