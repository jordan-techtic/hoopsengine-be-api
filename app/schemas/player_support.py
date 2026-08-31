"""Pydantic schemas for player Contact Support APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin
from app.schemas.profile import ProfileImageResponse

PLAYER_SUPPORT_INQUIRY_EXAMPLE = {
    "email": "user@example.com",
    "phone": "+15558392001",
    "inquiry_subject": "Technical Issue",
    "message_description": "Explain your problem or inquiry in detail here.",
}


class PlayerSupportInquiryRequest(BaseModel):
    """Payload for POST /api/v1/support/inquiries."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_SUPPORT_INQUIRY_EXAMPLE})

    email: str = Field(description="Contact email address", examples=["user@example.com"])
    phone: str = Field(
        description="Contact phone number (10–15 digits, formatting allowed)",
        examples=["+15558392001"],
    )
    inquiry_subject: str = Field(
        description=(
            "Selected inquiry subject from predefined options: "
            "Technical Issue, Billing Question, Account Help, Feature Request, Other"
        ),
        examples=["Technical Issue"],
    )
    message_description: str = Field(
        description="Support message body (max 500 characters)",
        examples=["Explain your problem or inquiry in detail here."],
    )


class PlayerSupportInquiryResponse(MobileWriteOnlyPasswordMixin):
    """Successful player support inquiry submission."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Your support request has been submitted successfully",
                "status": "submitted",
                "description": "We typically respond within 24 hours",
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "email": "user@example.com",
                "phone": "15558392001",
                "address": None,
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="submitted")
    description: str | None = Field(
        default="We typically respond within 24 hours",
        description="Response commitment shown after submission",
    )
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Created support request UUID")
    email: str = Field(description="Submitted contact email")
    phone: str = Field(description="Submitted contact phone (digits)")
    address: str | None = Field(
        default=None,
        description="Optional support address metadata for the mobile client",
    )


class PlayerSupportProfileData(BaseModel):
    """Support directory profile context for the Contact Support screen header."""

    name: str = Field(description="Support team display name")
    email: str = Field(description="Support team email address")
    phone: str = Field(description="Support team phone number")


class PlayerSupportContactResponse(MobileWriteOnlyPasswordMixin):
    """Player support directory contact details."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Support contact information loaded successfully",
                "status": "ready",
                "description": "Contact our support team by email or phone",
                "link": None,
                "error": None,
                "id": None,
                "name": "Support Team",
                "email": "support@hoopsengine.com",
                "phone": "+15558392001",
                "address": None,
                "profile": {
                    "name": "Support Team",
                    "email": "support@hoopsengine.com",
                    "phone": "+15558392001",
                },
                "avatar": None,
                "operating_hours": "Mon-Fri, 9am - 6pm EST",
                "live_chat_label": "Start instant chat",
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID | None = Field(default=None, description="Not applicable for contact info")
    name: str = Field(description="Support team display name for the screen header")
    email: str = Field(description="Support team email address")
    phone: str = Field(description="Support team phone number")
    address: str | None = Field(
        default=None,
        description="Optional support mailing or office address",
    )
    profile: PlayerSupportProfileData = Field(
        description="Nested support directory profile for the mobile header",
    )
    avatar: ProfileImageResponse | None = Field(
        default=None,
        description="Optional support team avatar metadata",
    )
    operating_hours: str = Field(
        description="Support team operating hours for the Support Directory section",
    )
    live_chat_label: str = Field(
        description="Label for the live chat action (e.g. Start instant chat)",
    )
