"""Organization admin custom UI design endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_access_token_session_id, get_current_org_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.org_custom_ui import (
    CustomDesignListResponse,
    CustomDesignSaveRequest,
    CustomDesignSaveResponse,
    UiDesignFeedbackRequest,
    UiDesignFeedbackResponse,
)
from app.services import org_custom_ui as org_custom_ui_service

router = APIRouter(prefix="/custom-ui", tags=["org-admin-custom-ui"])
ui_design_alias_router = APIRouter(prefix="/ui-design", tags=["org-admin-ui-design"])

AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing, invalid, expired, or revoked JWT",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
    403: openapi_error(
        "Authenticated user is not an organization admin",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Missing or invalid design fields",
        examples={
            "missing_template_name": {
                "code": "VALIDATION_ERROR",
                "message": "Template name is required",
                "details": [{"field": "template_name", "message": "Template name is required"}],
            },
            "missing_elements": {
                "code": "VALIDATION_ERROR",
                "message": "At least one design element is required",
                "details": [
                    {"field": "elements", "message": "At least one design element is required"}
                ],
            },
            "invalid_contrast": {
                "code": "VALIDATION_ERROR",
                "message": "Text color contrast does not meet WCAG AA requirements",
                "details": [
                    {
                        "field": "elements[0].text_color",
                        "message": "Text and background colors must have at least 4.5:1 contrast",
                    }
                ],
            },
        },
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

CONFLICT_ERROR_RESPONSES = {
    409: openapi_error_examples(
        "Approval required or feedback already submitted",
        examples={
            "approval_required": {
                "code": "APPROVAL_REQUIRED",
                "message": "Design approval is required before saving changes.",
                "details": [
                    {
                        "field": "approved",
                        "message": "Design approval is required before saving changes.",
                    }
                ],
            },
            "feedback_limit": {
                "code": "FEEDBACK_LIMIT_REACHED",
                "message": "Feedback has already been submitted for this session.",
                "details": [
                    {
                        "field": "feedback",
                        "message": "Feedback has already been submitted for this session.",
                    }
                ],
            },
        },
    ),
}

NOT_FOUND_RESPONSES = {
    404: openapi_error_examples(
        "Organization profile or design templates not found",
        examples={
            "organization_not_found": {
                "code": "ORGANIZATION_NOT_FOUND",
                "message": "Organization profile not found",
                "details": None,
            },
            "designs_not_found": {
                "code": "DESIGNS_NOT_FOUND",
                "message": "No design templates are available.",
                "details": None,
            },
            "design_not_found": {
                "code": "DESIGN_NOT_FOUND",
                "message": "Design template not found",
                "details": [{"field": "design_id", "message": "Design template not found"}],
            },
        },
    ),
}


@router.post(
    "/design",
    response_model=CustomDesignSaveResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="saveCustomUiDesign",
    summary="Save custom UI design template",
    description=(
        "Save a custom UI design template for the authenticated organization admin.\n\n"
        "**Required body fields:** `template_name`, `elements` (at least one), and "
        "`approved=true`.\n\n"
        "Each element requires `type` and `content`. Optional `text_color` and "
        "`background_color` hex values are validated for WCAG AA contrast on text elements.\n\n"
        "Returns **201** with a success message on save. Returns **400** when required fields "
        "are missing or contrast validation fails. Returns **409** when `approved` is false. "
        "Returns **404** when the admin is not linked to an organization.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def save_custom_ui_design(
    body: CustomDesignSaveRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> CustomDesignSaveResponse:
    """Save a custom UI design template."""
    payload = await org_custom_ui_service.save_custom_design(db, current_user, body)
    return CustomDesignSaveResponse(**payload)


@router.get(
    "/designs",
    response_model=CustomDesignListResponse,
    operation_id="listCustomUiDesigns",
    summary="List custom UI design templates",
    description=(
        "Retrieve saved custom UI design templates for the authenticated organization admin.\n\n"
        "Returns **200** with the available templates. Returns **404** when no designs exist "
        "for the organization. Returns **404** when the admin is not linked to an organization.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def list_custom_ui_designs(
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> CustomDesignListResponse:
    """Return available custom UI design templates."""
    payload = await org_custom_ui_service.list_design_templates(db, current_user)
    return CustomDesignListResponse(**payload)


@ui_design_alias_router.post(
    "/save",
    response_model=CustomDesignSaveResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="saveUiDesignTemplate",
    summary="Save customized UI design template (alias path)",
    description=(
        "Ticket-path alias for **POST /api/v1/custom-ui/design**.\n\n"
        "Save a custom UI design template using the same request body and validation rules.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def save_ui_design_template(
    body: CustomDesignSaveRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> CustomDesignSaveResponse:
    """Save a customized UI design template via the ui-design alias path."""
    payload = await org_custom_ui_service.save_custom_design(db, current_user, body)
    return CustomDesignSaveResponse(**payload)


@ui_design_alias_router.get(
    "/templates",
    response_model=CustomDesignListResponse,
    operation_id="listUiDesignTemplates",
    summary="List UI design templates (alias path)",
    description=(
        "Ticket-path alias for **GET /api/v1/custom-ui/designs**.\n\n"
        "Retrieve available design templates for the authenticated organization admin.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def list_ui_design_templates(
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> CustomDesignListResponse:
    """Return available UI design templates via the ui-design alias path."""
    payload = await org_custom_ui_service.list_design_templates(db, current_user)
    return CustomDesignListResponse(**payload)


@ui_design_alias_router.post(
    "/feedback",
    response_model=UiDesignFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="submitUiDesignFeedback",
    summary="Submit UI design feedback",
    description=(
        "Submit feedback on a custom UI design for the authenticated organization admin.\n\n"
        "**Required body field:** `feedback`.\n\n"
        "Optional `design_id` links feedback to a saved template. Optional `rating` accepts "
        "values from 1 to 5.\n\n"
        "Feedback is limited to **one submission per JWT session**.\n\n"
        "Returns **201** with a success message. Returns **409** when feedback was already "
        "submitted in the current session. Returns **404** when the referenced design or "
        "organization is not found.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def submit_ui_design_feedback(
    body: UiDesignFeedbackRequest,
    current_user: User = Depends(get_current_org_admin),
    session_token: str = Depends(get_access_token_session_id),
    db: AsyncSession = Depends(get_db),
) -> UiDesignFeedbackResponse:
    """Submit feedback on a UI design."""
    payload = await org_custom_ui_service.submit_design_feedback(
        db,
        current_user,
        body,
        session_token=session_token,
    )
    return UiDesignFeedbackResponse(**payload)
