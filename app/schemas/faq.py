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
        "Find quick answers to common questions about managing drills, "
        "subscriptions, and team sessions."
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
