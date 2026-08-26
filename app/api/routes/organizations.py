from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_super_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import ErrorResponse
from app.schemas.organization import (
    OrganizationCreateRequest,
    OrganizationDeleteResponse,
    OrganizationListResponse,
    OrganizationMutationResponse,
    OrganizationUpdateRequest,
)
from app.schemas.pagination import PaginationMeta
from app.services import organization as organization_service

router = APIRouter(prefix="/super-admin/organizations", tags=["admin-organizations"])

AUTH_ERROR_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Missing or invalid JWT"},
    403: {"model": ErrorResponse, "description": "User is not a super admin"},
    500: {"model": ErrorResponse, "description": "Unexpected server error"},
}


@router.get(
    "",
    response_model=OrganizationListResponse,
    summary="List organizations",
    description=(
        "Return a paginated list of organizations for the Super Admin Manage Organizations table.\n\n"
        "Each item includes `name`, `contact_email` / `email`, `phone_number` / `phone`, "
        "`address`, and `id` for edit/remove actions.\n\n"
        "An empty `items` array is a successful empty state.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def list_organizations(
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(
        default=None,
        description="Optional search against name, contact email, or phone number",
    ),
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> OrganizationListResponse:
    items, total = await organization_service.list_organizations(
        db,
        page=page,
        page_size=page_size,
        search=search,
    )
    meta = organization_service.build_pagination_meta(
        total=total,
        page=page,
        page_size=page_size,
    )
    return OrganizationListResponse(
        items=[organization_service.to_item(item) for item in items],
        pagination=PaginationMeta(**meta),
    )


@router.post(
    "",
    response_model=OrganizationMutationResponse,
    summary="Add a new organization",
    description=(
        "Create an organization with name, contact email, phone number, and address.\n\n"
        "A unique join code is generated automatically.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        400: {"model": ErrorResponse, "description": "Invalid organization data"},
        409: {"model": ErrorResponse, "description": "Could not create organization"},
        422: {"model": ErrorResponse, "description": "Request validation failed"},
    },
)
async def create_organization(
    payload: OrganizationCreateRequest,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMutationResponse:
    organization = await organization_service.create_organization(
        db,
        name=payload.name,
        contact_email=str(payload.contact_email),
        phone_number=payload.phone_number,
        address=payload.address,
    )
    return organization_service.to_mutation_response(
        organization,
        "Organization created successfully.",
    )


@router.put(
    "/{organization_id}",
    response_model=OrganizationMutationResponse,
    summary="Edit an existing organization",
    description=(
        "Partially update an organization by id. Send only the fields to change.\n\n"
        "Returns `404` when the organization does not exist.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        400: {"model": ErrorResponse, "description": "Invalid organization data"},
        404: {"model": ErrorResponse, "description": "Organization not found"},
        422: {"model": ErrorResponse, "description": "Request validation failed"},
    },
)
async def update_organization(
    organization_id: UUID,
    payload: OrganizationUpdateRequest,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMutationResponse:
    organization = await organization_service.update_organization(
        db,
        organization_id,
        name=payload.name,
        contact_email=str(payload.contact_email) if payload.contact_email is not None else None,
        phone_number=payload.phone_number,
        address=payload.address,
    )
    return organization_service.to_mutation_response(
        organization,
        "Organization updated successfully.",
    )


@router.delete(
    "/{organization_id}",
    response_model=OrganizationDeleteResponse,
    summary="Remove an organization",
    description=(
        "Remove an organization by id after the Super Admin confirms in the UI.\n\n"
        "Returns `404` if the organization does not exist. Returns `409` if related "
        "teams, coaches, players, or session data still reference it.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        404: {"model": ErrorResponse, "description": "Organization not found"},
        409: {"model": ErrorResponse, "description": "Organization has related records"},
    },
)
async def delete_organization(
    organization_id: UUID,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> OrganizationDeleteResponse:
    await organization_service.delete_organization(db, organization_id)
    return OrganizationDeleteResponse(message="Organization removed successfully.")
