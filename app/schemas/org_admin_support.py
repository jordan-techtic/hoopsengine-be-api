"""Pydantic schemas for organization admin Contact Support APIs (HE-413)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin
from app.schemas.profile import ProfileImageResponse

ORG_ADMIN_SUPPORT_CONTACT_REQUEST_EXAMPLE = {
    "email": "user@example.com",
    "phone": "+15558392001",
    "inquiry_subject": "Technical Issue",
    "message_description": "Explain your problem or inquiry in detail here.",
}

ORG_ADMIN_SUPPORT_CONTACT_RESPONSE_EXAMPLE = {
    "success": True,
    "message": "Your support request has been submitted successfully",
    "status": "submitted",
    "description": "We typically respond within 24 hours",
    "link": None,
    "error": None,
    "organization": "Hoops Engine",
    "id": "11111111-2222-3333-4444-555555555555",
    "request_id": "11111111-2222-3333-4444-555555555555",
    "email": "user@example.com",
    "phone": "15558392001",
    "phone_number": "15558392001",
    "address": None,
}

ORG_ADMIN_SUPPORT_CONFIRMATION_RESPONSE_EXAMPLE = {
    "success": True,
    "message": "Your support request has been submitted successfully",
    "status": "confirmed",
    "description": "We typically respond within 24 hours",
    "link": None,
    "error": None,
    "organization": "Hoops Engine",
    "id": "11111111-2222-3333-4444-555555555555",
    "email": "user@example.com",
    "phone": "15558392001",
    "phone_number": "15558392001",
    "address": None,
    "inquiry_subject": "Technical Issue",
    "message_description": "Explain your problem or inquiry in detail here.",
    "operating_hours": "Mon-Fri, 9am - 6pm EST",
    "live_chat_label": "Start instant chat",
}


class OrgAdminSupportContactRequest(BaseModel):
    """Payload for POST /admin/support/contact."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_SUPPORT_CONTACT_REQUEST_EXAMPLE})

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
        max_length=500,
        examples=["Explain your problem or inquiry in detail here."],
    )


class OrgAdminSupportContactResponse(MobileWriteOnlyPasswordMixin):
    """Successful organization admin support inquiry submission."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_SUPPORT_CONTACT_RESPONSE_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="submitted")
    description: str | None = Field(
        default="We typically respond within 24 hours",
        description="Response commitment shown after submission",
    )
    link: str | None = None
    error: None = None
    organization: str = Field(description="Support organization display name")
    id: UUID = Field(description="Created support request UUID")
    request_id: UUID = Field(description="Created support request UUID")
    email: str = Field(description="Submitted contact email")
    phone: str = Field(description="Submitted contact phone (digits)")
    phone_number: str = Field(description="Echo of submitted phone for mobile display")
    address: str | None = Field(
        default=None,
        description="Optional support mailing or office address",
    )


class OrgAdminSupportConfirmationResponse(MobileWriteOnlyPasswordMixin):
    """Confirmation details for a submitted organization admin support inquiry."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_SUPPORT_CONFIRMATION_RESPONSE_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="confirmed")
    description: str | None = Field(
        default="We typically respond within 24 hours",
        description="Response commitment shown on the confirmation screen",
    )
    link: str | None = None
    error: None = None
    organization: str = Field(description="Support organization display name")
    id: UUID | None = Field(
        default=None,
        description="Support request UUID when confirming a specific submission",
    )
    email: str | None = Field(default=None, description="Submitted contact email")
    phone: str | None = Field(default=None, description="Submitted or directory support phone")
    phone_number: str | None = Field(
        default=None,
        description="Echo of phone for mobile display",
    )
    address: str | None = Field(
        default=None,
        description="Optional support mailing or office address",
    )
    inquiry_subject: str | None = Field(
        default=None,
        description="Inquiry subject when confirming a specific submission",
    )
    message_description: str | None = Field(
        default=None,
        description="Submitted message when confirming a specific submission",
    )
    operating_hours: str = Field(description="Support team operating hours")
    live_chat_label: str = Field(description="Label for the live chat action")
    profile: dict[str, str] | None = Field(
        default=None,
        description="Nested support directory profile for the mobile header",
    )
    avatar: ProfileImageResponse | None = Field(
        default=None,
        description="Optional support team avatar metadata",
    )
