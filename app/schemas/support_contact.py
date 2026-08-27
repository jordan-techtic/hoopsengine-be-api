"""Pydantic schemas for public Contact Support JSON APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SUPPORT_CONTACT_CREATE_EXAMPLE = {
    "email": "user@example.com",
    "phone": "+15558392001",
    "inquiry_subject": "Technical Issue",
    "message_description": "Explain your problem or inquiry in detail here.",
}


class SupportContactCreateRequest(BaseModel):
    """Payload for POST /support/contact."""

    model_config = ConfigDict(json_schema_extra={"example": SUPPORT_CONTACT_CREATE_EXAMPLE})

    email: str = Field(description="Contact email address", examples=["user@example.com"])
    phone: str = Field(
        description="Contact phone number (10–15 digits, formatting allowed)",
        examples=["+15558392001"],
    )
    inquiry_subject: str = Field(
        description="Selected inquiry subject from predefined options",
        examples=["Technical Issue"],
    )
    message_description: str = Field(
        description="Support message body (max 500 characters)",
        examples=["Explain your problem or inquiry in detail here."],
    )


class SupportContactCreateResponse(BaseModel):
    """Successful public support message submission."""

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
                "request_id": "11111111-2222-3333-4444-555555555555",
                "email": "user@example.com",
                "phone": "15558392001",
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
    request_id: UUID = Field(description="Created support request UUID")
    email: str = Field(description="Submitted contact email")
    phone: str = Field(description="Submitted contact phone (digits)")


class SupportContactInfoResponse(BaseModel):
    """Public support directory contact details."""

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
                "email": "support@hoopsengine.com",
                "phone": "+15558392001",
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
    email: str = Field(description="Support team email address")
    phone: str = Field(description="Support team phone number")
