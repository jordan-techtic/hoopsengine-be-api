import logging
import math
import re
import secrets
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.organization import Organization
from app.schemas.organization import OrganizationItem, OrganizationMutationResponse

logger = logging.getLogger(__name__)

JOIN_CODE_ATTEMPTS = 8
PHONE_PATTERN = re.compile(r"^[+\d][\d\s().-]{6,30}$")

ORG_CHILD_CHECKS: tuple[tuple[str, str], ...] = (
    ("teams", "org_id"),
    ("subteams", "org_id"),
    ("coaches", "org_id"),
    ("players", "org_id"),
    ("practice_sessions", "org_id"),
    ("session_codes", "org_id"),
    ("session_data", "org_id"),
    ("user_roles", "org_id"),
    ("practice_plans", "org_id"),
    ("drill_submissions", "org_id"),
    ("drills", "submitted_by_org"),
)


def validate_phone_number(phone_number: str) -> str:
    """Return a stripped phone number or raise 400 if the format is invalid."""
    cleaned = phone_number.strip()
    if not PHONE_PATTERN.fullmatch(cleaned):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Enter a valid phone number",
            status_code=400,
            details=[{"field": "phone_number", "message": "Enter a valid phone number"}],
        )
    return cleaned


def validate_name(name: str) -> str:
    """Return a stripped organization name or raise 400 if empty."""
    cleaned = name.strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Organization name is required",
            status_code=400,
            details=[{"field": "name", "message": "Organization name is required"}],
        )
    return cleaned


def validate_address(address: str) -> str:
    """Return a stripped address or raise 400 if empty."""
    cleaned = address.strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Address is required",
            status_code=400,
            details=[{"field": "address", "message": "Address is required"}],
        )
    return cleaned


def generate_join_code() -> str:
    """Generate an 8-character uppercase join code."""
    return secrets.token_hex(4).upper()


def to_item(organization: Organization) -> OrganizationItem:
    """Map an Organization ORM row to the admin API item schema."""
    email = organization.admin_email
    phone = organization.phone_number
    return OrganizationItem(
        id=organization.id,
        name=organization.name,
        organization=organization.name,
        contact_email=email,
        email=email,
        phone_number=phone,
        phone=phone,
        address=organization.address,
        description=None,
        join_code=organization.join_code,
        created_at=organization.created_at,
    )


def to_mutation_response(organization: Organization, message: str) -> OrganizationMutationResponse:
    """Map an Organization ORM row to a create/update response with a message."""
    item = to_item(organization)
    return OrganizationMutationResponse(message=message, **item.model_dump())


def build_pagination_meta(total: int, page: int, page_size: int) -> dict[str, int | bool]:
    """Build list pagination metadata matching other admin list endpoints."""
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1 and total_pages > 0,
    }


async def get_organization_by_id(db: AsyncSession, organization_id: UUID) -> Organization | None:
    """Return an organization by id, or None if it does not exist."""
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    return result.scalar_one_or_none()


async def list_organizations(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    search: str | None = None,
) -> tuple[list[Organization], int]:
    """Return a page of organizations ordered by newest first."""
    filters = []
    if search and search.strip():
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                Organization.name.ilike(term),
                Organization.admin_email.ilike(term),
                Organization.phone_number.ilike(term),
            )
        )

    count_stmt = select(func.count()).select_from(Organization)
    list_stmt = select(Organization).order_by(Organization.created_at.desc().nulls_last())
    if filters:
        count_stmt = count_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)

    total = int(await db.scalar(count_stmt) or 0)
    result = await db.execute(
        list_stmt.offset((page - 1) * page_size).limit(page_size)
    )
    return list(result.scalars().all()), total


async def _allocate_join_code(db: AsyncSession) -> str:
    for _ in range(JOIN_CODE_ATTEMPTS):
        code = generate_join_code()
        existing = await db.execute(
            select(Organization.id).where(Organization.join_code == code)
        )
        if existing.scalar_one_or_none() is None:
            return code
    raise AppException(
        code="JOIN_CODE_GENERATION_FAILED",
        message="Could not generate a unique join code. Please try again.",
        status_code=500,
    )


async def create_organization(
    db: AsyncSession,
    *,
    name: str,
    contact_email: str,
    phone_number: str,
    address: str,
) -> Organization:
    """Create an organization row and persist it."""
    organization = Organization(
        name=validate_name(name),
        admin_email=str(contact_email).strip().lower(),
        phone_number=validate_phone_number(phone_number),
        address=validate_address(address),
        join_code=await _allocate_join_code(db),
    )
    db.add(organization)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        logger.warning("Integrity error creating organization name=%s", name)
        raise AppException(
            code="ORGANIZATION_CREATE_FAILED",
            message="Could not create the organization. Please try again.",
            status_code=409,
        ) from None
    await db.refresh(organization)
    logger.info("Created organization %s (%s)", organization.id, organization.name)
    return organization


async def update_organization(
    db: AsyncSession,
    organization_id: UUID,
    *,
    name: str | None = None,
    contact_email: str | None = None,
    phone_number: str | None = None,
    address: str | None = None,
) -> Organization:
    """Update the given organization. Raises 404 if it does not exist."""
    organization = await get_organization_by_id(db, organization_id)
    if organization is None:
        raise AppException(
            code="ORGANIZATION_NOT_FOUND",
            message="Organization not found",
            status_code=404,
        )

    if name is None and contact_email is None and phone_number is None and address is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one organization field must be provided",
            status_code=400,
        )

    if name is not None:
        organization.name = validate_name(name)
    if contact_email is not None:
        organization.admin_email = str(contact_email).strip().lower()
    if phone_number is not None:
        organization.phone_number = validate_phone_number(phone_number)
    if address is not None:
        organization.address = validate_address(address)

    await db.commit()
    await db.refresh(organization)
    logger.info("Updated organization %s", organization.id)
    return organization


async def _table_exists(db: AsyncSession, table_name: str) -> bool:
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :table_name
            )
            """
        ),
        {"table_name": table_name},
    )
    return bool(exists)


async def _column_exists(db: AsyncSession, table_name: str, column_name: str) -> bool:
    """Return True when ``public.{table_name}.{column_name}`` exists."""
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND column_name = :column_name
            )
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return bool(exists)


async def organization_has_dependencies(db: AsyncSession, organization_id: UUID) -> bool:
    """Return True if client-domain rows still reference this organization."""
    for table_name, column_name in ORG_CHILD_CHECKS:
        if not await _table_exists(db, table_name):
            continue
        if not await _column_exists(db, table_name, column_name):
            continue
        exists = await db.scalar(
            text(
                f"""
                SELECT EXISTS (
                    SELECT 1 FROM {table_name}
                    WHERE {column_name} = :org_id
                    LIMIT 1
                )
                """
            ),
            {"org_id": organization_id},
        )
        if exists:
            return True
    return False


async def delete_organization(db: AsyncSession, organization_id: UUID) -> None:
    """Hard-delete an organization that has no dependent rows. Raises 404/409."""
    organization = await get_organization_by_id(db, organization_id)
    if organization is None:
        raise AppException(
            code="ORGANIZATION_NOT_FOUND",
            message="Organization not found",
            status_code=404,
        )

    if await organization_has_dependencies(db, organization_id):
        raise AppException(
            code="ORGANIZATION_HAS_DEPENDENCIES",
            message=(
                "This organization cannot be removed because it still has related "
                "teams, coaches, players, or session data."
            ),
            status_code=409,
        )

    await db.delete(organization)
    await db.commit()
    logger.info("Deleted organization %s", organization_id)
