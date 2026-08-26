from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_super_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error
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

ORG_ID_PATH = Path(
    ...,
    description="Organization UUID from the table row being edited or removed",
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
        "Request validation failed (invalid UUID, empty required fields, or invalid email)",
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=[{"field": "contact_email", "message": "value is not a valid email address"}],
    ),
}

INVALID_ORG_DATA_RESPONSE = {
    400: openapi_error(
        "Invalid organization data (phone format, empty name/address after trim, or empty update)",
        code="VALIDATION_ERROR",
        message="Enter a valid phone number",
        details=[{"field": "phone_number", "message": "Enter a valid phone number"}],
    ),
}

NOT_FOUND_RESPONSE = {
    404: openapi_error(
        "Organization not found",
        code="ORGANIZATION_NOT_FOUND",
        message="Organization not found",
    ),
}


@router.get(
    "",
    response_model=OrganizationListResponse,
    operation_id="listOrganizations",
    summary="List organizations",
    description=(
        "Return a paginated list of organizations for the Super Admin Manage Organizations table.\n\n"
        "Each item includes `id`, `name` / `organization`, `contact_email` / `email`, "
        "`phone_number` / `phone`, `address`, and `join_code` so the UI can render columns "
        "and edit/remove actions.\n\n"
        "`search` matches name, contact email, or phone (case-insensitive). "
        "An empty `items` array is a successful empty state, not an error.\n\n"
        "**Requires super admin JWT** (`Authorization: Bearer <access_token>`)."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def list_organizations(
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
    search: str | None = Query(
        default=None,
        description="Optional search against name, contact email, or phone number",
        examples=["Organization Name"],
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
    operation_id="createOrganization",
    summary="Add a new organization",
    description=(
        "Create an organization from the Manage Organizations Add form: `name`, "
        "`contact_email`, `phone_number`, and `address` (all required).\n\n"
        "A unique 8-character `join_code` is generated automatically. "
        "Invalid phone format returns `400 VALIDATION_ERROR`. "
        "Invalid or empty fields return `422`. "
        "A unique-constraint failure returns `409 ORGANIZATION_CREATE_FAILED`.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **INVALID_ORG_DATA_RESPONSE,
        409: openapi_error(
            "Could not create organization (join code or uniqueness conflict)",
            code="ORGANIZATION_CREATE_FAILED",
            message="Could not create the organization. Please try again.",
        ),
        **VALIDATION_ERROR_RESPONSE,
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
    operation_id="updateOrganization",
    summary="Edit an existing organization",
    description=(
        "Partially update an organization by id. Send only the fields to change "
        "(`name`, `contact_email`, `phone_number`, `address`).\n\n"
        "An empty body returns `400 VALIDATION_ERROR`. "
        "Unknown id returns `404 ORGANIZATION_NOT_FOUND`. "
        "Invalid phone returns `400`. Invalid UUID path returns `422`.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **INVALID_ORG_DATA_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def update_organization(
    payload: OrganizationUpdateRequest,
    organization_id: UUID = ORG_ID_PATH,
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
    operation_id="deleteOrganization",
    summary="Remove an organization",
    description=(
        "Remove an organization by id after the Super Admin confirms in the UI.\n\n"
        "Returns `404 ORGANIZATION_NOT_FOUND` if it does not exist. "
        "Returns `409 ORGANIZATION_HAS_DEPENDENCIES` if related teams, coaches, "
        "players, or session data still reference it. "
        "Invalid UUID path returns `422`.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSE,
        409: openapi_error(
            "Organization has related records and cannot be removed",
            code="ORGANIZATION_HAS_DEPENDENCIES",
            message=(
                "This organization cannot be removed because it still has related "
                "teams, coaches, players, or session data."
            ),
        ),
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def delete_organization(
    organization_id: UUID = ORG_ID_PATH,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> OrganizationDeleteResponse:
    await organization_service.delete_organization(db, organization_id)
    return OrganizationDeleteResponse(message="Organization removed successfully.")
