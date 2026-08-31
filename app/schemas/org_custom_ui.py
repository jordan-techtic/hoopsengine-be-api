"""Pydantic schemas for organization admin custom UI design API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

DESIGN_ELEMENT_EXAMPLE = {
    "type": "text",
    "content": "Sample Text",
    "text_color": "#1A1A1A",
    "background_color": "#FFFFFF",
}

CUSTOM_DESIGN_SAVE_EXAMPLE = {
    "template_name": "Custom Design Template",
    "elements": [DESIGN_ELEMENT_EXAMPLE],
    "approved": True,
}

UI_DESIGN_FEEDBACK_EXAMPLE = {
    "feedback": "The layout is intuitive and easy to navigate.",
    "design_id": "11111111-2222-3333-4444-555555555555",
    "rating": 5,
}

SUPPORTED_ELEMENT_TYPES = frozenset({"text", "image", "button", "section"})


class DesignElement(BaseModel):
    """Single UI design element within a template."""

    model_config = ConfigDict(json_schema_extra={"example": DESIGN_ELEMENT_EXAMPLE})

    type: str = Field(
        description="Element type (text, image, button, section)",
        examples=["text"],
    )
    content: str = Field(
        description="Element content or label",
        examples=["Sample Text"],
    )
    text_color: str | None = Field(
        default=None,
        description="Optional hex text color used for WCAG AA contrast validation",
        examples=["#1A1A1A"],
    )
    background_color: str | None = Field(
        default=None,
        description="Optional hex background color used for WCAG AA contrast validation",
        examples=["#FFFFFF"],
    )

    @field_validator("type")
    @classmethod
    def normalize_type(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("Element type is required")
        return cleaned

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        return value.strip()


class CustomDesignSaveRequest(BaseModel):
    """Payload for POST /custom-ui/design and POST /ui-design/save."""

    model_config = ConfigDict(json_schema_extra={"example": CUSTOM_DESIGN_SAVE_EXAMPLE})

    template_name: str = Field(
        description="Custom design template display name",
        examples=["Custom Design Template"],
    )
    elements: list[DesignElement] = Field(
        description="Ordered list of UI elements in the design template",
        min_length=1,
    )
    approved: bool = Field(
        default=False,
        description="Admin approval flag — must be true before the design can be saved",
        examples=[True],
    )


class CustomDesignItem(BaseModel):
    """Saved custom UI design template."""

    id: UUID = Field(description="Design template identifier")
    template_name: str = Field(description="Template display name")
    elements: list[DesignElement] = Field(description="Saved UI elements")
    status: str = Field(description="Template status indicator")
    created_at: datetime = Field(description="UTC timestamp when the template was saved")
    updated_at: datetime = Field(description="UTC timestamp when the template was last updated")


class CustomDesignSaveResponse(BaseModel):
    """Successful custom design save response."""

    success: bool = Field(default=True)
    message: str = Field(description="Human-readable confirmation message")
    data: CustomDesignItem = Field(description="Saved design template")
    error: None = Field(default=None)


class CustomDesignListResponse(BaseModel):
    """List of available custom UI design templates."""

    success: bool = Field(default=True)
    message: str = Field(description="Human-readable outcome message")
    data: list[CustomDesignItem] = Field(description="Available design templates")
    error: None = Field(default=None)


class UiDesignFeedbackRequest(BaseModel):
    """Payload for POST /ui-design/feedback."""

    model_config = ConfigDict(json_schema_extra={"example": UI_DESIGN_FEEDBACK_EXAMPLE})

    feedback: str = Field(
        description="Feedback comment about the UI design",
        examples=["The layout is intuitive and easy to navigate."],
    )
    design_id: UUID | None = Field(
        default=None,
        description="Optional saved design template the feedback refers to",
        examples=["11111111-2222-3333-4444-555555555555"],
    )
    rating: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Optional 1–5 star rating",
        examples=[5],
    )

    @field_validator("feedback")
    @classmethod
    def normalize_feedback(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Feedback is required")
        return cleaned


class UiDesignFeedbackData(BaseModel):
    """Feedback metadata returned after submission."""

    feedback_id: UUID = Field(description="Persisted feedback identifier")
    design_id: UUID | None = Field(default=None, description="Related design template, if any")
    rating: int | None = Field(default=None, description="Submitted rating, if any")
    status: Literal["submitted"] = Field(default="submitted")


class UiDesignFeedbackResponse(BaseModel):
    """Successful UI design feedback submission response."""

    success: bool = Field(default=True)
    message: str = Field(description="Human-readable confirmation message")
    data: UiDesignFeedbackData = Field(description="Submitted feedback metadata")
    error: None = Field(default=None)
