"""Business logic for organization admin profile management."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.organization import Organization
from app.models.user import User
from app.schemas.org_admin_profile import OrganizationProfileUpdateRequest
from app.services import account_settings as account_settings_service
from app.services import profile as profile_service
from app.services.organization import (
    get_organization_by_id,
    validate_address,
    validate_name,
    validate_phone_number,
)

logger = logging.getLogger(__name__)


async def _email_in_use(db: AsyncSession, *, email: str, exclude_user_id: UUID) -> bool:
    """Return True when another user already owns the email address."""
    result = await db.execute(
        select(User.id).where(
            User.email == email,
            User.id != exclude_user_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def require_admin_organization(db: AsyncSession, user: User) -> Organization:
    """Return the org admin's organization or raise 404."""
    if user.org_id is None:
        raise AppException(
            code="ORGANIZATION_NOT_FOUND",
            message="Organization profile not found",
            status_code=404,
        )
    organization = await get_organization_by_id(db, user.org_id)
    if organization is None:
        raise AppException(
            code="ORGANIZATION_NOT_FOUND",
            message="Organization profile not found",
            status_code=404,
        )
    return organization


def validate_organization_description(description: str) -> str:
    """Return a stripped organization description or raise 400 when empty."""
    cleaned = description.strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Organization description is required",
            status_code=400,
            details=[{"field": "description", "message": "Organization description is required"}],
        )
    return cleaned


def validate_contact_info(contact_info: str) -> str:
    """Return normalized contact info when it is a valid email or phone number."""
    cleaned = contact_info.strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Contact information is required",
            status_code=400,
            details=[{"field": "contact_info", "message": "Contact information is required"}],
        )
    try:
        return str(TypeAdapter(EmailStr).validate_python(cleaned)).strip().lower()
    except ValidationError:
        pass
    try:
        return validate_phone_number(cleaned)
    except AppException as exc:
        if exc.details and exc.details[0].get("field") == "phone_number":
            raise AppException(
                code="VALIDATION_ERROR",
                message="Enter a valid email address or phone number",
                status_code=400,
                details=[
                    {
                        "field": "contact_info",
                        "message": "Enter a valid email address or phone number",
                    }
                ],
            ) from exc
        raise


def _resolve_contact_info(organization: Organization) -> str | None:
    """Return persisted contact info or a composed fallback from legacy fields."""
    if organization.contact_info:
        return organization.contact_info
    parts: list[str] = []
    if organization.admin_email:
        parts.append(organization.admin_email)
    if organization.phone_number:
        parts.append(organization.phone_number)
    return " | ".join(parts) if parts else None


def _is_management_update(payload: OrganizationProfileUpdateRequest) -> bool:
    """Return True when the Organization Profile Management payload is used."""
    management_signals = (
        payload.name is not None,
        payload.description is not None,
        payload.contact_info is not None,
    )
    detailed_signals = (
        payload.organization_name is not None,
        payload.address is not None,
        payload.email is not None,
        payload.phone_number is not None,
        payload.first_name is not None,
        payload.last_name is not None,
    )
    if any(detailed_signals):
        return False
    return any(management_signals)


def _build_avatar(organization: Organization, user: User) -> dict[str, Any] | None:
    """Build avatar payload from organization logo or admin profile image."""
    if organization.logo_url:
        return {"url": organization.logo_url, "original_name": None, "content_type": None}
    return profile_service.build_coach_avatar(user)


def build_organization_profile_payload(
    user: User,
    organization: Organization,
    *,
    message: str,
    status: str = "ready",
    description: str | None = None,
) -> dict[str, Any]:
    """Map organization and admin user rows to the profile API envelope."""
    phone_number = organization.phone_number
    organization_description = organization.profile_description
    contact_info = _resolve_contact_info(organization)
    nested = {
        "organization_name": organization.name,
        "address": organization.address,
        "email": organization.admin_email,
        "phone_number": phone_number,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "organization_description": organization_description,
        "contact_info": contact_info,
    }
    return {
        "success": True,
        "message": message,
        "status": status,
        "description": description,
        "link": None,
        "error": None,
        "title": "Edit Organization Profile",
        "id": organization.id,
        "name": organization.name,
        "organization": organization.name,
        "organization_name": organization.name,
        "address": organization.address,
        "email": organization.admin_email,
        "phone_number": phone_number,
        "phone": phone_number,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "organization_description": organization_description,
        "contact_info": contact_info,
        "avatar": _build_avatar(organization, user),
        "profile": nested,
    }


async def get_organization_profile(db: AsyncSession, user: User) -> dict[str, Any]:
    """Return the authenticated org admin's organization profile."""
    organization = await require_admin_organization(db, user)
    return build_organization_profile_payload(
        user,
        organization,
        message="Organization profile loaded successfully",
        status="ready",
        description="Review and update your organization details",
    )


async def _update_management_profile(
    db: AsyncSession,
    user: User,
    organization: Organization,
    payload: OrganizationProfileUpdateRequest,
) -> dict[str, Any]:
    """Update organization profile using name, description, and contact_info fields."""
    name = validate_name(payload.name or "")
    organization_description = validate_organization_description(payload.description or "")
    contact_info = validate_contact_info(payload.contact_info or "")

    if await account_settings_service.organization_name_exists(
        db,
        name=name,
        exclude_org_id=organization.id,
    ):
        raise AppException(
            code="ORGANIZATION_NAME_EXISTS",
            message="An organization with this name already exists",
            status_code=409,
            details=[
                {
                    "field": "name",
                    "message": "An organization with this name already exists",
                }
            ],
        )

    organization.name = name
    organization.profile_description = organization_description
    organization.contact_info = contact_info

    if "@" in contact_info:
        if contact_info != user.email.lower() and await _email_in_use(
            db,
            email=contact_info,
            exclude_user_id=user.id,
        ):
            raise AppException(
                code="EMAIL_ALREADY_IN_USE",
                message="This email is already in use by another account",
                status_code=409,
                details=[
                    {
                        "field": "contact_info",
                        "message": "This email is already in use by another account",
                    }
                ],
            )
        organization.admin_email = contact_info
    else:
        organization.phone_number = contact_info

    user.updated_at = account_settings_service._utcnow()

    await db.commit()
    await db.refresh(organization)
    await db.refresh(user)

    logger.info(
        "Org admin %s updated organization management profile %s",
        user.id,
        organization.id,
    )

    return build_organization_profile_payload(
        user,
        organization,
        message="Organization profile updated successfully",
        status="saved",
        description="Your organization details have been saved",
    )


async def update_organization_profile(
    db: AsyncSession,
    user: User,
    payload: OrganizationProfileUpdateRequest,
) -> dict[str, Any]:
    """
    Update organization profile fields and the linked admin user's name/email.

    Raises 400 for missing or invalid fields.
    Raises 404 when no organization is linked.
    Raises 409 for duplicate organization name or email.
    """
    organization = await require_admin_organization(db, user)

    if _is_management_update(payload):
        return await _update_management_profile(db, user, organization, payload)

    organization_name = account_settings_service._ensure_non_empty(
        payload.organization_name or "",
        field="organization_name",
        label="Organization name",
    )
    address = validate_address(payload.address or "")
    phone_number = validate_phone_number(payload.phone_number or "")
    email = profile_service.validate_profile_email(payload.email or "")
    first_name = account_settings_service._ensure_non_empty(
        payload.first_name or "",
        field="first_name",
        label="First name",
    )
    last_name = account_settings_service._ensure_non_empty(
        payload.last_name or "",
        field="last_name",
        label="Last name",
    )
    organization_name = validate_name(organization_name)

    if await account_settings_service.organization_name_exists(
        db,
        name=organization_name,
        exclude_org_id=organization.id,
    ):
        raise AppException(
            code="ORGANIZATION_NAME_EXISTS",
            message="An organization with this name already exists",
            status_code=409,
            details=[
                {
                    "field": "organization_name",
                    "message": "An organization with this name already exists",
                }
            ],
        )

    if email != user.email.lower():
        if await _email_in_use(db, email=email, exclude_user_id=user.id):
            raise AppException(
                code="EMAIL_ALREADY_IN_USE",
                message="This email is already in use by another account",
                status_code=409,
                details=[
                    {
                        "field": "email",
                        "message": "This email is already in use by another account",
                    }
                ],
            )
        user.email = email

    organization.name = organization_name
    organization.address = address
    organization.admin_email = email
    organization.phone_number = phone_number
    user.first_name = first_name
    user.last_name = last_name
    user.updated_at = account_settings_service._utcnow()

    await db.commit()
    await db.refresh(organization)
    await db.refresh(user)

    logger.info("Org admin %s updated organization profile %s", user.id, organization.id)

    return build_organization_profile_payload(
        user,
        organization,
        message="Organization profile updated successfully",
        status="saved",
        description="Your organization details have been saved",
    )
