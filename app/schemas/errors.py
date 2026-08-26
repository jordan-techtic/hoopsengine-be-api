from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """Machine-readable error payload nested under `error`."""

    code: str = Field(
        description="Stable error code the client can switch on (e.g. ORGANIZATION_NOT_FOUND)",
        examples=["VALIDATION_ERROR"],
    )
    message: str = Field(
        description="Human-readable message safe to show in the UI",
        examples=["Request validation failed"],
    )
    details: Any | None = Field(
        default=None,
        description="Optional field-level details (validation errors, conflicting field, etc.)",
        examples=[[{"field": "contact_email", "message": "value is not a valid email address"}]],
    )


class ErrorResponse(BaseModel):
    """Standard API error envelope used by all documented error responses."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": [
                        {"field": "contact_email", "message": "value is not a valid email address"}
                    ],
                },
            }
        }
    )

    success: bool = Field(
        default=False,
        description="Always `false` for error responses",
        examples=[False],
    )
    error: ErrorDetail = Field(description="Error code, message, and optional details")


class SuccessResponse(BaseModel):
    success: bool = Field(default=True, description="Always `true` for this envelope")
    message: str = Field(description="Human-readable success message")
    data: Any | None = Field(default=None, description="Optional success payload")


def openapi_error(
    description: str,
    *,
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    """Build a FastAPI `responses` entry using the standard error envelope plus example."""
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {
            "application/json": {
                "example": {
                    "success": False,
                    "error": {
                        "code": code,
                        "message": message,
                        "details": details,
                    },
                }
            }
        },
    }
