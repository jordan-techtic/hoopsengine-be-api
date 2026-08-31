"""Unit tests for organization admin custom UI design service helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.schemas.org_custom_ui import CustomDesignSaveRequest, DesignElement
from app.services.org_custom_ui import validate_design_element, validate_design_payload


def test_validate_design_payload_success() -> None:
    payload = CustomDesignSaveRequest(
        template_name="Training Dashboard",
        elements=[DesignElement(type="text", content="Welcome")],
        approved=True,
    )
    template_name, elements = validate_design_payload(payload)
    assert template_name == "Training Dashboard"
    assert elements == [{"type": "text", "content": "Welcome"}]


def test_validate_design_payload_missing_approval_409() -> None:
    payload = CustomDesignSaveRequest(
        template_name="Training Dashboard",
        elements=[DesignElement(type="text", content="Welcome")],
        approved=False,
    )
    with pytest.raises(AppException) as exc_info:
        validate_design_payload(payload)
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "APPROVAL_REQUIRED"


def test_validate_design_element_low_contrast_400() -> None:
    element = DesignElement(
        type="text",
        content="Low contrast",
        text_color="#CCCCCC",
        background_color="#FFFFFF",
    )
    with pytest.raises(AppException) as exc_info:
        validate_design_element(element, 0)
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_validate_design_element_supported_contrast_passes() -> None:
    element = DesignElement(
        type="text",
        content="Readable text",
        text_color="#1A1A1A",
        background_color="#FFFFFF",
    )
    normalized = validate_design_element(element, 0)
    assert normalized["text_color"] == "#1A1A1A"
