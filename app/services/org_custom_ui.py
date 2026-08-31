"""Business logic for organization admin custom UI design management."""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.org_ui_design import OrgUiDesign, OrgUiDesignFeedback
from app.models.user import User
from app.schemas.org_custom_ui import (
    CustomDesignSaveRequest,
    DesignElement,
    SUPPORTED_ELEMENT_TYPES,
    UiDesignFeedbackRequest,
)
from app.services.org_admin_profile import require_admin_organization

logger = logging.getLogger(__name__)

HEX_COLOR_PATTERN = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")
WCAG_AA_NORMAL_TEXT_RATIO = 4.5
SAVE_SUCCESS_MESSAGE = "Custom design saved successfully."
LIST_SUCCESS_MESSAGE = "Design templates loaded successfully."
FEEDBACK_SUCCESS_MESSAGE = "Feedback submitted successfully."
NO_DESIGNS_MESSAGE = "No design templates are available."
APPROVAL_REQUIRED_MESSAGE = "Design approval is required before saving changes."
FEEDBACK_LIMIT_MESSAGE = "Feedback has already been submitted for this session."


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    """Convert a hex color string to normalized RGB floats."""
    normalized = hex_color.strip()
    if len(normalized) == 4:
        normalized = "#" + "".join(char * 2 for char in normalized[1:])
    red = int(normalized[1:3], 16) / 255.0
    green = int(normalized[3:5], 16) / 255.0
    blue = int(normalized[5:7], 16) / 255.0
    return red, green, blue


def _channel_luminance(channel: float) -> float:
    """Compute relative luminance for a single RGB channel."""
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    """Return WCAG relative luminance for a hex color."""
    red, green, blue = _hex_to_rgb(hex_color)
    return (
        0.2126 * _channel_luminance(red)
        + 0.7152 * _channel_luminance(green)
        + 0.0722 * _channel_luminance(blue)
    )


def _contrast_ratio(foreground: str, background: str) -> float:
    """Return the WCAG contrast ratio between two hex colors."""
    lighter = max(_relative_luminance(foreground), _relative_luminance(background))
    darker = min(_relative_luminance(foreground), _relative_luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def _validate_hex_color(value: str, *, field: str) -> str:
    """Return a normalized hex color or raise 400 when invalid."""
    cleaned = value.strip().upper()
    if not HEX_COLOR_PATTERN.fullmatch(cleaned):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Enter a valid hex color",
            status_code=400,
            details=[{"field": field, "message": "Color must use #RRGGBB or #RGB format"}],
        )
    if len(cleaned) == 4:
        return "#" + "".join(char * 2 for char in cleaned[1:])
    return cleaned


def validate_design_element(element: DesignElement, index: int) -> dict[str, Any]:
    """Validate a single design element and return a normalized dict for persistence."""
    field_prefix = f"elements[{index}]"
    element_type = element.type.strip().lower()
    if element_type not in SUPPORTED_ELEMENT_TYPES:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Element type is not supported",
            status_code=400,
            details=[
                {
                    "field": f"{field_prefix}.type",
                    "message": f"Supported types: {', '.join(sorted(SUPPORTED_ELEMENT_TYPES))}",
                }
            ],
        )
    if not element.content:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Element content is required",
            status_code=400,
            details=[{"field": f"{field_prefix}.content", "message": "Element content is required"}],
        )

    normalized: dict[str, Any] = {
        "type": element_type,
        "content": element.content,
    }

    if element.text_color is not None:
        normalized["text_color"] = _validate_hex_color(
            element.text_color,
            field=f"{field_prefix}.text_color",
        )
    if element.background_color is not None:
        normalized["background_color"] = _validate_hex_color(
            element.background_color,
            field=f"{field_prefix}.background_color",
        )

    if element_type == "text" and normalized.get("text_color") and normalized.get("background_color"):
        ratio = _contrast_ratio(normalized["text_color"], normalized["background_color"])
        if ratio < WCAG_AA_NORMAL_TEXT_RATIO:
            raise AppException(
                code="VALIDATION_ERROR",
                message="Text color contrast does not meet WCAG AA requirements",
                status_code=400,
                details=[
                    {
                        "field": f"{field_prefix}.text_color",
                        "message": (
                            "Text and background colors must have at least "
                            f"{WCAG_AA_NORMAL_TEXT_RATIO}:1 contrast"
                        ),
                    }
                ],
            )

    return normalized


def validate_design_payload(payload: CustomDesignSaveRequest) -> tuple[str, list[dict[str, Any]]]:
    """Validate save payload fields and return normalized template data."""
    template_name = payload.template_name.strip()
    if not template_name:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Template name is required",
            status_code=400,
            details=[{"field": "template_name", "message": "Template name is required"}],
        )
    if not payload.elements:
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one design element is required",
            status_code=400,
            details=[{"field": "elements", "message": "At least one design element is required"}],
        )
    if not payload.approved:
        raise AppException(
            code="APPROVAL_REQUIRED",
            message=APPROVAL_REQUIRED_MESSAGE,
            status_code=409,
            details=[{"field": "approved", "message": APPROVAL_REQUIRED_MESSAGE}],
        )

    normalized_elements = [
        validate_design_element(element, index) for index, element in enumerate(payload.elements)
    ]
    return template_name, normalized_elements


def _to_design_item(design: OrgUiDesign) -> dict[str, Any]:
    """Map an OrgUiDesign row to the API item schema."""
    return {
        "id": design.id,
        "template_name": design.template_name,
        "elements": design.elements,
        "status": design.status,
        "created_at": design.created_at,
        "updated_at": design.updated_at,
    }


async def save_custom_design(
    db: AsyncSession,
    user: User,
    payload: CustomDesignSaveRequest,
) -> dict[str, Any]:
    """Persist a custom UI design template for the authenticated org admin's organization."""
    organization = await require_admin_organization(db, user)
    template_name, elements = validate_design_payload(payload)

    design = OrgUiDesign(
        org_id=organization.id,
        created_by_user_id=user.id,
        template_name=template_name,
        elements=elements,
        status="saved",
    )
    db.add(design)
    await db.commit()
    await db.refresh(design)

    logger.info("Org admin %s saved custom UI design %s", user.id, design.id)

    return {
        "success": True,
        "message": SAVE_SUCCESS_MESSAGE,
        "data": _to_design_item(design),
        "error": None,
    }


async def list_design_templates(db: AsyncSession, user: User) -> dict[str, Any]:
    """Return saved design templates for the authenticated org admin's organization."""
    organization = await require_admin_organization(db, user)

    result = await db.execute(
        select(OrgUiDesign)
        .where(OrgUiDesign.org_id == organization.id)
        .order_by(OrgUiDesign.updated_at.desc())
    )
    designs = result.scalars().all()
    if not designs:
        raise AppException(
            code="DESIGNS_NOT_FOUND",
            message=NO_DESIGNS_MESSAGE,
            status_code=404,
        )

    return {
        "success": True,
        "message": LIST_SUCCESS_MESSAGE,
        "data": [_to_design_item(design) for design in designs],
        "error": None,
    }


async def _require_design_for_org(
    db: AsyncSession,
    *,
    design_id: UUID,
    org_id: UUID,
) -> OrgUiDesign:
    """Return a design belonging to the organization or raise 404."""
    result = await db.execute(
        select(OrgUiDesign).where(
            OrgUiDesign.id == design_id,
            OrgUiDesign.org_id == org_id,
        )
    )
    design = result.scalar_one_or_none()
    if design is None:
        raise AppException(
            code="DESIGN_NOT_FOUND",
            message="Design template not found",
            status_code=404,
            details=[{"field": "design_id", "message": "Design template not found"}],
        )
    return design


async def submit_design_feedback(
    db: AsyncSession,
    user: User,
    payload: UiDesignFeedbackRequest,
    *,
    session_token: str,
) -> dict[str, Any]:
    """Persist UI design feedback limited to one submission per JWT session."""
    organization = await require_admin_organization(db, user)

    if payload.design_id is not None:
        await _require_design_for_org(
            db,
            design_id=payload.design_id,
            org_id=organization.id,
        )

    existing = await db.execute(
        select(OrgUiDesignFeedback.id).where(
            OrgUiDesignFeedback.org_id == organization.id,
            OrgUiDesignFeedback.user_id == user.id,
            OrgUiDesignFeedback.session_token == session_token,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise AppException(
            code="FEEDBACK_LIMIT_REACHED",
            message=FEEDBACK_LIMIT_MESSAGE,
            status_code=409,
            details=[{"field": "feedback", "message": FEEDBACK_LIMIT_MESSAGE}],
        )

    feedback_row = OrgUiDesignFeedback(
        org_id=organization.id,
        user_id=user.id,
        session_token=session_token,
        design_id=payload.design_id,
        feedback=payload.feedback,
        rating=payload.rating,
    )
    db.add(feedback_row)
    await db.commit()
    await db.refresh(feedback_row)

    logger.info("Org admin %s submitted UI design feedback %s", user.id, feedback_row.id)

    return {
        "success": True,
        "message": FEEDBACK_SUCCESS_MESSAGE,
        "data": {
            "feedback_id": feedback_row.id,
            "design_id": feedback_row.design_id,
            "rating": feedback_row.rating,
            "status": "submitted",
        },
        "error": None,
    }
