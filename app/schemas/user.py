from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.enums import UserRole
from app.schemas.pagination import PaginationMeta

ROLE_ALIASES = {
    "coach": UserRole.COACH,
    "player": UserRole.PLAYER,
    "org_admin": UserRole.ORG_ADMIN,
    "organization_admin": UserRole.ORG_ADMIN,
    "super_admin": UserRole.SUPER_ADMIN,
    "superadmin": UserRole.SUPER_ADMIN,
}


def normalize_role_value(value: str) -> UserRole:
    """Map ticket/UI labels such as `Coach` onto `UserRole` values."""
    key = value.strip().lower().replace(" ", "_")
    role = ROLE_ALIASES.get(key)
    if role is None:
        raise ValueError("Role must be coach, player, org_admin, or super_admin")
    return role


class RoleOption(BaseModel):
    value: str = Field(description="Role value stored on the user", examples=["coach"])
    label: str = Field(description="Label shown in the Manage Users role dropdown", examples=["Coach"])
    description: str = Field(description="Short explanation of the role")


class AdminUserCreateRequest(BaseModel):
    """Payload for creating a user from Super Admin Manage Users."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "John",
                "last_name": "Doe",
                "name": "John Doe",
                "email": "john.doe@example.com",
                "password": "Coach@123",
                "role": "coach",
            }
        }
    )

    first_name: str = Field(
        min_length=1,
        max_length=255,
        description="User first name",
        examples=["John"],
    )
    last_name: str = Field(
        min_length=1,
        max_length=255,
        description="User last name",
        examples=["Doe"],
    )
    name: str | None = Field(
        default=None,
        max_length=255,
        description="Full display name (optional; derived from first and last name when omitted)",
        examples=["John Doe"],
    )
    email: EmailStr = Field(
        description="Login email address (must be unique)",
        examples=["john.doe@example.com"],
    )
    password: str = Field(
        min_length=8,
        max_length=72,
        description=(
            "Initial password. Minimum 8 characters with uppercase, lowercase, "
            "number, and special character."
        ),
        examples=["Coach@123"],
    )
    role: UserRole = Field(
        description="Account role. Use `coach` or `player` for the Manage Users page.",
        examples=["coach"],
    )
    org_id: UUID | None = Field(
        default=None,
        description="Optional organization UUID to attach the user to",
    )

    @field_validator("first_name", "last_name", "name")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field cannot be empty")
        return cleaned

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("role", mode="before")
    @classmethod
    def coerce_role(cls, value: object) -> object:
        if isinstance(value, str):
            return normalize_role_value(value)
        return value


class AdminUserUpdateRequest(BaseModel):
    """Partial payload for editing a user."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "John",
                "last_name": "Doe",
                "name": "John Doe",
                "email": "john.doe@example.com",
                "role": "coach",
            }
        }
    )

    first_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="User first name",
        examples=["John"],
    )
    last_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="User last name",
        examples=["Doe"],
    )
    name: str | None = Field(
        default=None,
        max_length=255,
        description="Full display name; splits into first and last name when those fields are omitted",
        examples=["John Doe"],
    )
    email: EmailStr | None = Field(
        default=None,
        description="Login email address (must be unique)",
        examples=["john.doe@example.com"],
    )
    password: str | None = Field(
        default=None,
        min_length=8,
        max_length=72,
        description="Optional new password (same complexity rules as create)",
        examples=["Coach@123"],
    )
    role: UserRole | None = Field(
        default=None,
        description="Account role",
        examples=["player"],
    )
    org_id: UUID | None = Field(
        default=None,
        description="Optional organization UUID. Send null to clear.",
    )

    @field_validator("first_name", "last_name", "name")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field cannot be empty")
        return cleaned

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip().lower() or None
        return value

    @field_validator("role", mode="before")
    @classmethod
    def coerce_role(cls, value: object) -> object:
        if isinstance(value, str):
            return normalize_role_value(value)
        return value

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "AdminUserUpdateRequest":
        if not any(
            [
                self.first_name is not None,
                self.last_name is not None,
                self.name is not None,
                self.email is not None,
                self.password is not None,
                self.role is not None,
                "org_id" in self.model_fields_set,
            ]
        ):
            raise ValueError("At least one user field must be provided")
        return self


class AdminUserItem(BaseModel):
    """User row for the Super Admin Manage Users table and forms."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "11111111-2222-3333-4444-555555555555",
                "first_name": "John",
                "last_name": "Doe",
                "name": "John Doe",
                "email": "john.doe@example.com",
                "role": "coach",
                "roles": ["coach"],
                "description": None,
                "org_id": None,
                "is_super_admin": False,
                "is_active": True,
                "is_self": False,
                "last_sign_in_at": None,
                "created_at": "2026-08-26T10:00:00.000000Z",
            }
        },
    )

    id: UUID = Field(description="User UUID")
    first_name: str | None = Field(default=None, description="First name")
    last_name: str | None = Field(default=None, description="Last name")
    name: str = Field(description="Display name for the users table")
    email: EmailStr = Field(description="Login email")
    role: UserRole = Field(description="Assigned role")
    roles: list[str] = Field(description="Assigned role as a one-item list for table/filter binding")
    description: str | None = Field(
        default=None,
        description="Optional description; not collected on the Manage Users form",
    )
    org_id: UUID | None = Field(default=None, description="Attached organization, if any")
    is_super_admin: bool = Field(description="Whether this account is a super admin")
    is_active: bool = Field(description="Whether the account can sign in")
    is_self: bool = Field(description="True when this row is the authenticated super admin (disable Remove)")
    last_sign_in_at: datetime | None = None
    created_at: datetime | None = None


class AdminUserMutationResponse(BaseModel):
    """Create/update success payload with user data and a toast message."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "User created successfully.",
                "id": "11111111-2222-3333-4444-555555555555",
                "first_name": "John",
                "last_name": "Doe",
                "name": "John Doe",
                "email": "john.doe@example.com",
                "role": "coach",
                "roles": ["coach"],
                "description": None,
                "org_id": None,
                "is_super_admin": False,
                "is_active": True,
                "is_self": False,
                "last_sign_in_at": None,
                "created_at": "2026-08-26T10:00:00.000000Z",
            }
        }
    )

    message: str = Field(description="UI-safe success message for toast notifications")
    id: UUID
    first_name: str | None = None
    last_name: str | None = None
    name: str
    email: EmailStr
    role: UserRole
    roles: list[str]
    description: str | None = None
    org_id: UUID | None = None
    is_super_admin: bool
    is_active: bool
    is_self: bool
    last_sign_in_at: datetime | None = None
    created_at: datetime | None = None


class AdminUserListResponse(BaseModel):
    items: list[AdminUserItem]
    pagination: PaginationMeta
    roles: list[RoleOption] = Field(
        description="Assignable roles for the Add/Edit User dropdown (Coach, Player, and others)",
    )


class AdminUserDeleteResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"message": "User removed successfully."}},
    )

    message: str = Field(description="UI-safe success message")
