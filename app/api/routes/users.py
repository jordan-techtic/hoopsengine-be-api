from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_super_admin
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.errors import openapi_error
from app.schemas.pagination import PaginationMeta
from app.schemas.user import (
    AdminUserCreateRequest,
    AdminUserDeleteResponse,
    AdminUserListResponse,
    AdminUserMutationResponse,
    AdminUserUpdateRequest,
)
from app.services import user as user_service

router = APIRouter(prefix="/super-admin/users", tags=["super-admin-users"])

USER_ID_PATH = Path(
    ...,
    description="User UUID from the table row being edited or removed",
    examples=["11111111-2222-3333-4444-555555555555"],
)

AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing or invalid JWT",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
    403: openapi_error(
        "User is not a super admin",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
    500: openapi_error(
        "Unexpected server error",
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred",
    ),
}

VALIDATION_ERROR_RESPONSE = {
    422: openapi_error(
        "Request validation failed (invalid UUID, empty fields, invalid email, or unknown role)",
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=[{"field": "email", "message": "value is not a valid email address"}],
    ),
}

INVALID_USER_DATA_RESPONSE = {
    400: openapi_error(
        "Invalid user data (password complexity, empty name, or unknown org_id)",
        code="VALIDATION_ERROR",
        message="Password must include at least one uppercase letter",
        details=[
            {
                "field": "password",
                "message": "Password must include at least one uppercase letter",
            }
        ],
    ),
}

NOT_FOUND_RESPONSE = {
    404: openapi_error(
        "User not found (or already removed)",
        code="USER_NOT_FOUND",
        message="User not found",
    ),
}

EMAIL_CONFLICT_RESPONSE = {
    409: openapi_error(
        "Email already in use by another account",
        code="EMAIL_ALREADY_IN_USE",
        message="This email is already in use by another account",
        details=[
            {
                "field": "email",
                "message": "This email is already in use by another account",
            }
        ],
    ),
}


@router.get(
    "",
    response_model=AdminUserListResponse,
    operation_id="listUsers",
    summary="List users",
    description=(
        "Return a paginated list of users for the Super Admin Manage Users table.\n\n"
        "Each item includes `id`, `first_name`, `last_name`, `name`, `email`, "
        "`role` / `roles`, and `is_self` so the UI can disable Remove on the "
        "signed-in super admin.\n\n"
        "`roles` on the list response is the Add/Edit dropdown catalog "
        "(Coach, Player, Organization Admin, Super Admin). "
        "`role` query filter accepts `coach`, `player`, `org_admin`, or `super_admin`. "
        "`search` matches name and email. Soft-deleted users are omitted. "
        "An empty `items` array is a successful empty state.\n\n"
        "**Requires super admin JWT** (`Authorization: Bearer <access_token>`)."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def list_users(
    page: int = Query(
        default=1,
        ge=1,
        description="1-based page number",
        examples=[1],
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Items per page",
        examples=[20],
    ),
    role: UserRole | None = Query(
        default=None,
        description="Optional filter: `coach`, `player`, `org_admin`, or `super_admin`",
        examples=["coach"],
    ),
    search: str | None = Query(
        default=None,
        description="Optional search against name and email",
        examples=["john.doe@example.com"],
    ),
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserListResponse:
    items, total = await user_service.list_users(
        db,
        page=page,
        page_size=page_size,
        role=role,
        search=search,
    )
    meta = user_service.build_pagination_meta(total=total, page=page, page_size=page_size)
    return AdminUserListResponse(
        items=[
            user_service.to_item(item, current_user_id=current_user.id) for item in items
        ],
        pagination=PaginationMeta(**meta),
        roles=user_service.assignable_roles(),
    )


@router.post(
    "",
    response_model=AdminUserMutationResponse,
    operation_id="createUser",
    summary="Add a new user",
    description=(
        "Create a user from the Manage Users Add form: `first_name`, `last_name`, "
        "`email`, `password`, and `role` (Coach or Player for the FE form). "
        "Optional `name` and `org_id` are accepted.\n\n"
        "Password is write-only and is never returned. "
        "Weak passwords (including `password123`) return `400 VALIDATION_ERROR`. "
        "Duplicate emails return `409 EMAIL_ALREADY_IN_USE`. "
        "Unknown `org_id` returns `400 ORGANIZATION_NOT_FOUND`. "
        "UI labels `Coach` / `Player` are coerced to `coach` / `player`.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **INVALID_USER_DATA_RESPONSE,
        **EMAIL_CONFLICT_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def create_user(
    payload: AdminUserCreateRequest,
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserMutationResponse:
    user = await user_service.create_user(
        db,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=str(payload.email),
        password=payload.password,
        role=payload.role,
        org_id=payload.org_id,
    )
    return user_service.to_mutation_response(
        user,
        "User created successfully.",
        current_user_id=current_user.id,
    )


@router.put(
    "/{user_id}",
    response_model=AdminUserMutationResponse,
    operation_id="updateUser",
    summary="Edit an existing user",
    description=(
        "Partially update a user by id. Send only the fields to change. "
        "`password` is optional and write-only. `name` splits into first/last "
        "when those fields are omitted.\n\n"
        "Empty body returns `422`. Unknown or removed user returns `404 USER_NOT_FOUND`. "
        "Duplicate email returns `409`. Unknown `org_id` returns `400 ORGANIZATION_NOT_FOUND`.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **INVALID_USER_DATA_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **EMAIL_CONFLICT_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def update_user(
    payload: AdminUserUpdateRequest,
    user_id: UUID = USER_ID_PATH,
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserMutationResponse:
    user = await user_service.update_user(
        db,
        user_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        name=payload.name,
        email=str(payload.email) if payload.email is not None else None,
        password=payload.password,
        role=payload.role,
        org_id=payload.org_id,
        org_id_set="org_id" in payload.model_fields_set,
    )
    return user_service.to_mutation_response(
        user,
        "User updated successfully.",
        current_user_id=current_user.id,
    )


@router.delete(
    "/{user_id}",
    response_model=AdminUserDeleteResponse,
    operation_id="deleteUser",
    summary="Remove a user",
    description=(
        "Soft-delete a user by id. The signed-in super admin cannot remove their own "
        "account (`400 CANNOT_DELETE_SELF`) so the UI can disable that action via `is_self`.\n\n"
        "Returns `404 USER_NOT_FOUND` if the user does not exist or was already removed. "
        "Invalid UUID path returns `422`. The user disappears from subsequent list calls.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        400: openapi_error(
            "Cannot remove own account",
            code="CANNOT_DELETE_SELF",
            message="You cannot remove your own account",
        ),
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def delete_user(
    user_id: UUID = USER_ID_PATH,
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserDeleteResponse:
    await user_service.delete_user(db, user_id, current_user_id=current_user.id)
    return AdminUserDeleteResponse(message="User removed successfully.")
