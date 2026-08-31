"""Pydantic schemas for public FAQs APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin

FAQ_LIST_EXAMPLE = {
    "success": True,
    "message": "FAQs loaded successfully",
    "status": "ready",
    "title": "How can we help you?",
    "description": (
        "Find quick answers to common questions about joining sessions, "
        "viewing drills, and tracking your progress."
    ),
    "link": "/api/v1/support/contact",
    "error": None,
    "id": None,
    "phone": "+15558392001",
    "faqs": [
        {
            "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "question": "How do I create a new drill?",
            "answer": (
                "You can create a new drill by going to the drills section "
                "and selecting 'Create Drill'."
            ),
        },
        {
            "id": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
            "question": "How do I manage my subscription?",
            "answer": (
                "Go to your Profile Settings and select 'Subscription'. "
                "From there, you can view your active Pro Plan."
            ),
        },
    ],
}


class FaqItem(BaseModel):
    """One FAQ entry for the FAQs screen."""

    id: UUID = Field(description="Stable identifier for the FAQ row")
    question: str = Field(description="FAQ question text shown in the list")
    answer: str = Field(description="FAQ answer revealed when the question is tapped")


class FaqsListResponse(MobileWriteOnlyPasswordMixin):
    """GET /faqs response for the public FAQs screen."""

    model_config = ConfigDict(json_schema_extra={"example": FAQ_LIST_EXAMPLE})

    success: bool = Field(default=True)
    message: str = Field(description="UI-safe summary for load/submit states")
    status: str = Field(
        default="ready",
        description="Screen state: ready when FAQs exist, empty when none are configured",
    )
    title: str = Field(description="Intro banner title")
    description: str | None = Field(
        default=None,
        description="Intro banner subtitle shown below the title",
    )
    link: str | None = Field(
        default=None,
        description="Support contact path for the Contact Support button",
    )
    error: None = None
    id: UUID | None = Field(
        default=None,
        description="Not applicable for FAQ list responses",
    )
    phone: str = Field(description="Support phone number for the support card")
    faqs: list[FaqItem] = Field(description="Expandable FAQ question and answer rows")


FAQ_CONTACT_SUPPORT_EXAMPLE = {
    "email": "user@example.com",
    "phone": "+15558392001",
    "inquiry_subject": "Technical Issue",
    "message_description": "Need help from the FAQs screen.",
}


class FaqContactSupportRequest(BaseModel):
    """Payload for POST /faqs/contact-support."""

    model_config = ConfigDict(json_schema_extra={"example": FAQ_CONTACT_SUPPORT_EXAMPLE})

    email: str = Field(description="Contact email address", examples=["user@example.com"])
    phone: str = Field(
        description="Contact phone number (10–15 digits, formatting allowed)",
        examples=["+15558392001"],
    )
    inquiry_subject: str = Field(
        ...,
        description=(
            "Selected inquiry subject from predefined options: "
            "Technical Issue, Billing Question, Account Help, Feature Request, Other"
        ),
        examples=["Technical Issue"],
    )
    message_description: str = Field(
        ...,
        max_length=500,
        description="Support message body (max 500 characters)",
        examples=["Need help from the FAQs screen."],
    )


class FaqContactSupportResponse(MobileWriteOnlyPasswordMixin):
    """Successful FAQ contact-support submission."""

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
                "phone": "15558392001",
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="submitted")
    description: str | None = Field(default="We typically respond within 24 hours")
    link: str | None = None
    error: None = None
    id: UUID
    phone: str


class FaqDetailResponse(MobileWriteOnlyPasswordMixin):
    """GET /faqs/{faq_id} response for a single FAQ item."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "FAQ loaded successfully",
                "status": "ready",
                "title": "How can we help you?",
                "description": (
                    "Find quick answers to common questions about joining sessions, "
                    "viewing drills, and tracking your progress."
                ),
                "link": "/api/v1/support/contact",
                "error": None,
                "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "phone": "+15558392001",
                "question": "How do I join a training session?",
                "answer": "Open the Sessions tab and tap Join Session.",
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str
    title: str
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID
    phone: str
    question: str
    answer: str
