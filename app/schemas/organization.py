from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.pagination import PaginationMeta

ORG_EXAMPLE_ID = "11111111-2222-3333-4444-555555555555"
ORG_REQUEST_EXAMPLE = {
    "name": "Organization Name",
    "contact_email": "contact@example.com",
    "phone_number": "1234567890",
    "address": "123 Main St",
}
ORG_ITEM_EXAMPLE = {
    "id": ORG_EXAMPLE_ID,
    "name": "Organization Name",
    "organization": "Organization Name",
    "contact_email": "contact@example.com",
    "email": "contact@example.com",
    "phone_number": "1234567890",
    "phone": "1234567890",
    "address": "123 Main St",
    "description": None,
    "join_code": "A1B2C3D4",
    "created_at": "2026-08-26T10:00:00.000000Z",
}


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class OrganizationCreateRequest(BaseModel):
    """Payload for creating an organization (Manage Organizations Add form)."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_REQUEST_EXAMPLE})

    name: str = Field(
        min_length=1,
        max_length=255,
        description="Organization name shown in the admin table",
        examples=["Organization Name"],
    )
    contact_email: EmailStr = Field(
        description="Primary contact email for the organization",
        examples=["contact@example.com"],
    )
    phone_number: str = Field(
        min_length=1,
        max_length=32,
        description="Contact phone number (digits, spaces, parentheses, dashes, optional leading +)",
        examples=["1234567890"],
    )
    address: str = Field(
        min_length=1,
        max_length=500,
        description="Organization street address",
        examples=["123 Main St"],
    )

    @field_validator("name", "phone_number", "address")
    @classmethod
    def strip_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field cannot be empty")
        return cleaned

    @field_validator("contact_email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class OrganizationUpdateRequest(BaseModel):
    """Partial payload for updating an organization. Send only fields to change."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_REQUEST_EXAMPLE})

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Organization name shown in the admin table",
        examples=["Organization Name"],
    )
    contact_email: EmailStr | None = Field(
        default=None,
        description="Primary contact email for the organization",
        examples=["contact@example.com"],
    )
    phone_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=32,
        description="Contact phone number (digits, spaces, parentheses, dashes, optional leading +)",
        examples=["1234567890"],
    )
    address: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="Organization street address",
        examples=["123 Main St"],
    )

    @field_validator("name", "phone_number", "address")
    @classmethod
    def strip_optional_required_when_sent(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("contact_email", mode="before")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip().lower() or None
        return value


class OrganizationItem(BaseModel):
    """Organization row returned to the Super Admin UI table."""

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"example": ORG_ITEM_EXAMPLE})

    id: UUID = Field(description="Organization UUID", examples=[ORG_EXAMPLE_ID])
    name: str = Field(description="Organization name", examples=["Organization Name"])
    organization: str = Field(
        description="Organization name (alias for frontend table binding)",
        examples=["Organization Name"],
    )
    contact_email: EmailStr = Field(
        description="Primary contact email",
        examples=["contact@example.com"],
    )
    email: EmailStr = Field(
        description="Primary contact email (alias of contact_email)",
        examples=["contact@example.com"],
    )
    phone_number: str | None = Field(
        default=None,
        description="Contact phone number",
        examples=["1234567890"],
    )
    phone: str | None = Field(
        default=None,
        description="Contact phone number (alias of phone_number)",
        examples=["1234567890"],
    )
    address: str | None = Field(
        default=None,
        description="Street address",
        examples=["123 Main St"],
    )
    description: str | None = Field(
        default=None,
        description="Optional description; not collected on the Manage Organizations form",
    )
    join_code: str | None = Field(
        default=None,
        description="Unique join code generated on create",
        examples=["A1B2C3D4"],
    )
    created_at: datetime | None = Field(
        default=None,
        description="When the organization was created",
        examples=["2026-08-26T10:00:00.000000Z"],
    )


class OrganizationMutationResponse(BaseModel):
    """Create/update success payload with organization data and a UI message."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Organization created successfully.",
                **ORG_ITEM_EXAMPLE,
            }
        }
    )

    message: str = Field(
        description="UI-safe success message",
        examples=["Organization created successfully."],
    )
    id: UUID = Field(description="Organization UUID", examples=[ORG_EXAMPLE_ID])
    name: str = Field(description="Organization name", examples=["Organization Name"])
    organization: str = Field(
        description="Organization name (alias for frontend table binding)",
        examples=["Organization Name"],
    )
    contact_email: EmailStr = Field(
        description="Primary contact email",
        examples=["contact@example.com"],
    )
    email: EmailStr = Field(
        description="Primary contact email (alias of contact_email)",
        examples=["contact@example.com"],
    )
    phone_number: str | None = Field(
        default=None,
        description="Contact phone number",
        examples=["1234567890"],
    )
    phone: str | None = Field(
        default=None,
        description="Contact phone number (alias of phone_number)",
        examples=["1234567890"],
    )
    address: str | None = Field(
        default=None,
        description="Street address",
        examples=["123 Main St"],
    )
    description: str | None = Field(
        default=None,
        description="Optional description; not collected on the Manage Organizations form",
    )
    join_code: str | None = Field(
        default=None,
        description="Unique join code generated on create",
        examples=["A1B2C3D4"],
    )
    created_at: datetime | None = Field(
        default=None,
        description="When the organization was created",
        examples=["2026-08-26T10:00:00.000000Z"],
    )


class OrganizationListResponse(BaseModel):
    """Paginated organization list for the Manage Organizations table."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [ORG_ITEM_EXAMPLE],
                "pagination": {
                    "page": 1,
                    "page_size": 20,
                    "total": 1,
                    "total_pages": 1,
                    "has_next": False,
                    "has_prev": False,
                },
            }
        }
    )

    items: list[OrganizationItem] = Field(
        description="Organizations on this page. Empty array is a successful empty state.",
    )
    pagination: PaginationMeta = Field(description="Page metadata for the table")


class OrganizationDeleteResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"message": "Organization removed successfully."},
        }
    )

    message: str = Field(
        description="UI-safe success message",
        examples=["Organization removed successfully."],
    )
