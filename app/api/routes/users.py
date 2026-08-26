from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_super_admin
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.errors import ErrorResponse
from app.schemas.pagination import PaginationMeta
from app.schemas.user import (
    AdminUserCreateRequest,
    AdminUserDeleteResponse,
    AdminUserListResponse,
    AdminUserMutationResponse,
    AdminUserUpdateRequest,
)
from app.services import user as user_service

router = APIRouter(prefix="/super-admin/users", tags=["admin-users"])

AUTH_ERROR_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Missing or invalid JWT"},
    403: {"model": ErrorResponse, "description": "User is not a super admin"},
    500: {"model": ErrorResponse, "description": "Unexpected server error"},
}


@router.get(
    "",
    response_model=AdminUserListResponse,
    summary="List users",
    description=(
        "Return a paginated list of users for the Super Admin Manage Users table.\n\n"
        "Each item includes `id`, `name`, `email`, `role` / `roles`, and `is_self` "
        "so the UI can disable Remove on the signed-in super admin.\n\n"
        "`roles` on the list response is the dropdown catalog (Coach, Player, and others).\n\n"
        "An empty `items` array is a successful empty state.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def list_users(
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    role: UserRole | None = Query(
        default=None,
        description="Optional filter: `coach`, `player`, `org_admin`, or `super_admin`",
    ),
    search: str | None = Query(
        default=None,
        description="Optional search against name and email",
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
    summary="Add a new user",
    description=(
        "Create a user with first name, last name, email, password, and role.\n\n"
        "Password is write-only and is never returned. Duplicate emails return `409`.\n\n"
        "Role values: `coach`, `player`, `org_admin`, `super_admin` "
        "(the UI may also send `Coach` / `Player`).\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        400: {"model": ErrorResponse, "description": "Invalid user data"},
        409: {"model": ErrorResponse, "description": "Email already in use"},
        422: {"model": ErrorResponse, "description": "Request validation failed"},
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
    summary="Edit an existing user",
    description=(
        "Partially update a user by id. Send only the fields to change. "
        "Password is optional and write-only.\n\n"
        "Returns `404` when the user does not exist (or was removed).\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        400: {"model": ErrorResponse, "description": "Invalid user data"},
        404: {"model": ErrorResponse, "description": "User not found"},
        409: {"model": ErrorResponse, "description": "Email already in use"},
        422: {"model": ErrorResponse, "description": "Request validation failed"},
    },
)
async def update_user(
    user_id: UUID,
    payload: AdminUserUpdateRequest,
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
    summary="Remove a user",
    description=(
        "Soft-delete a user by id. The signed-in super admin cannot remove their own account "
        "(`400 CANNOT_DELETE_SELF`) so the UI can disable that action.\n\n"
        "Returns `404` if the user does not exist.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        400: {"model": ErrorResponse, "description": "Cannot remove own account"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
)
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserDeleteResponse:
    await user_service.delete_user(db, user_id, current_user_id=current_user.id)
    return AdminUserDeleteResponse(message="User removed successfully.")
