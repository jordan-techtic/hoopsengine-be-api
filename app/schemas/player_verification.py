"""Request and response schemas for player cancel verification endpoints."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlayerCancelVerificationInstructionsResponse(BaseModel):
    """Cancel verification screen copy for the player signup flow."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Cancel verification instructions loaded.",
                "status": "ready",
                "description": (
                    "Confirming cancellation will stop verification and remove your signup progress."
                ),
                "link": "http://localhost:3000/verify-email",
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "heading": "Cancel Verification?",
                "instructions": (
                    "Cancelling will stop the verification process. You will lose your progress "
                    "and may need to start the signup process again."
                ),
                "phone": "+1-555-0100",
            }
        }
    )

    success: bool = Field(default=True, description="Always true when instructions are returned")
    message: str = Field(description="Human-readable status message for the UI")
    status: str = Field(default="ready", description="Screen readiness status for the mobile client")
    description: str | None = Field(
        default=None,
        description="Secondary copy explaining the consequences of cancelling verification",
    )
    link: str | None = Field(
        default=None,
        description="Deep link for the Continue Verification button",
    )
    error: None = Field(default=None, description="Always null on success")
    id: UUID = Field(description="Authenticated user UUID")
    heading: str = Field(description="Primary headline shown in the message container")
    instructions: str = Field(description="Instructional body copy for the cancel verification screen")
    phone: str | None = Field(
        default=None,
        description="Optional phone metadata echoed from the status bar query parameter",
    )
