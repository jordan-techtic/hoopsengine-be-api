"""Business logic for Account Settings APIs."""

from __future__ import annotations

import logging
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.security import hash_password, verify_password
from app.models.enums import UserRole
from app.models.organization import Organization
from app.models.support_request import SupportRequest
from app.models.user import User
from app.schemas.account_settings import (
    AccountProfileUpdateRequest,
    AuthKeysRequest,
    ChangePasswordRequest,
    OrganizationSettingsRequest,
    PushNotificationsRequest,
    SupportSubmitRequest,
)
from app.schemas.profile import CoachProfileUpdateRequest
from app.services import profile as profile_service
from app.services.organization import get_organization_by_id, validate_name
from app.services.user import validate_password

logger = logging.getLogger(__name__)

AUTH_KEYS_META_KEY = "auth_keys"
PUSH_NOTIFICATIONS_META_KEY = "push_notifications_enabled"
NUMERIC_PHONE_PATTERN = re.compile(r"^\d{10,15}$")

DEFAULT_HELP_ARTICLES: list[dict[str, str]] = [
    {
        "question": "How do I create a new drill?",
        "answer": (
            "You can create a new drill by going to the drills section "
            "and selecting 'Create Drill'."
        ),
    },
    {
        "question": "How do I manage my subscription?",
        "answer": (
            "Go to your Profile Settings and select 'Subscription'. "
            "From there, you can view your active Pro Plan."
        ),
    },
    {
        "question": "How do I change my password?",
        "answer": "Open Account Settings and choose Change Password to update your credentials.",
    },
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_non_empty(value: str | None, *, field: str, label: str) -> str:
    """Return stripped text or raise 400 when empty."""
    if value is None or not value.strip():
        raise AppException(
            code="VALIDATION_ERROR",
            message=f"{label} is required",
            status_code=400,
            details=[{"field": field, "message": f"{label} is required"}],
        )
    return value.strip()


def split_full_name(full_name: str) -> tuple[str, str]:
    """Split a full name into first and last name components."""
    cleaned = full_name.strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Full name is required",
            status_code=400,
            details=[{"field": "full_name", "message": "Full name is required"}],
        )
    parts = cleaned.split(None, 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def get_user_meta(user: User) -> dict[str, Any]:
    """Return a mutable copy of the user's JSON metadata."""
    return deepcopy(user.raw_user_meta_data or {})


def set_user_meta(user: User, meta: dict[str, Any]) -> None:
    """Persist JSON metadata on the user row."""
    user.raw_user_meta_data = meta
    user.updated_at = _utcnow()


def get_auth_keys(user: User) -> dict[str, str]:
    """Return stored authentication keys from user metadata."""
    meta = user.raw_user_meta_data or {}
    keys = meta.get(AUTH_KEYS_META_KEY)
    if not isinstance(keys, dict):
        return {}
    return {str(key): str(value) for key, value in keys.items() if value is not None}


def get_push_notifications_enabled(user: User) -> bool:
    """Return whether push notifications are enabled for the user."""
    meta = user.raw_user_meta_data or {}
    value = meta.get(PUSH_NOTIFICATIONS_META_KEY)
    return bool(value)


def validate_numeric_phone(phone: str) -> str:
    """Validate that a phone number contains only digits (10–15 digits)."""
    digits = re.sub(r"\D", "", phone.strip())
    if not NUMERIC_PHONE_PATTERN.fullmatch(digits):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Phone number must contain 10 to 15 digits",
            status_code=400,
            details=[{"field": "phone", "message": "Phone number must contain 10 to 15 digits"}],
        )
    return digits


def validate_support_subject(subject: str) -> str:
    """Validate inquiry subject against configured options."""
    cleaned = _ensure_non_empty(subject, field="inquiry_subject", label="Inquiry subject")
    allowed = {item.strip().lower() for item in settings.SUPPORT_INQUIRY_SUBJECTS}
    if cleaned.lower() not in allowed:
        raise AppException(
            code="INVALID_INQUIRY_SUBJECT",
            message="Inquiry subject must be selected from the predefined options",
            status_code=409,
            details=[
                {
                    "field": "inquiry_subject",
                    "message": "Inquiry subject must be selected from the predefined options",
                }
            ],
        )
    return cleaned


def validate_support_message(message: str) -> str:
    """Validate support message length."""
    cleaned = _ensure_non_empty(
        message,
        field="message_description",
        label="Message description",
    )
    if len(cleaned) > settings.SUPPORT_MESSAGE_MAX_LENGTH:
        raise AppException(
            code="VALIDATION_ERROR",
            message=f"Message must be {settings.SUPPORT_MESSAGE_MAX_LENGTH} characters or fewer",
            status_code=400,
            details=[
                {
                    "field": "message_description",
                    "message": (
                        f"Message must be {settings.SUPPORT_MESSAGE_MAX_LENGTH} characters or fewer"
                    ),
                }
            ],
        )
    return cleaned


def get_help_articles() -> list[dict[str, str]]:
    """Return configured help articles with defaults."""
    articles = settings.HELP_SUPPORT_ARTICLES or DEFAULT_HELP_ARTICLES
    return [{"question": item["question"], "answer": item["answer"]} for item in articles]


def get_support_contact_info() -> dict[str, str]:
    """Return public support contact information."""
    return {
        "email": settings.SUPPORT_CONTACT_EMAIL,
        "phone": settings.SUPPORT_CONTACT_PHONE,
    }


def build_profile_summary(user: User) -> dict[str, Any]:
    """Build profile header summary for account settings responses."""
    full_name = profile_service.build_coach_display_name(user)
    profile_data = profile_service.build_coach_profile_data(user)
    return {
        "id": user.id,
        "name": full_name,
        "full_name": full_name,
        "role": user.role,
        "profile": profile_data,
    }


async def organization_name_exists(
    db: AsyncSession,
    *,
    name: str,
    exclude_org_id: UUID,
) -> bool:
    """Return True when another organization already uses the given name."""
    normalized = name.strip().lower()
    if not normalized:
        return False
    result = await db.execute(
        select(Organization.id).where(
            func.lower(func.trim(Organization.name)) == normalized,
            Organization.id != exclude_org_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def change_password(
    db: AsyncSession,
    user: User,
    payload: ChangePasswordRequest,
) -> User:
    """
    Change the authenticated user's password after verifying the current password.

    Raises 400 for empty, incorrect, or weak passwords.
    Raises 409 when the new password matches the current password.
    """
    current = _ensure_non_empty(
        payload.current_password,
        field="current_password",
        label="Current password",
    )
    new_password = _ensure_non_empty(
        payload.new_password,
        field="new_password",
        label="New password",
    )

    if not verify_password(current, user.encrypted_password):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Current password is incorrect",
            status_code=400,
            details=[{"field": "current_password", "message": "Current password is incorrect"}],
        )

    validate_password(new_password)

    if verify_password(new_password, user.encrypted_password):
        raise AppException(
            code="PASSWORD_UNCHANGED",
            message="New password must be different from your current password",
            status_code=409,
            details=[
                {
                    "field": "new_password",
                    "message": "New password must be different from your current password",
                }
            ],
        )

    user.encrypted_password = hash_password(new_password)
    user.recovery_token = None
    user.recovery_sent_at = None
    user.updated_at = _utcnow()
    await db.commit()
    await db.refresh(user)
    logger.info("User %s changed password via account settings", user.id)
    return user


async def update_organization_settings(
    db: AsyncSession,
    user: User,
    payload: OrganizationSettingsRequest,
) -> Organization:
    """
    Update the coach's organization name.

    Raises 400 when the user has no organization or name is empty.
    Raises 404 when the organization does not exist.
    Raises 409 when the name is already used by another organization.
    """
    if user.org_id is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="You are not associated with an organization",
            status_code=400,
            details=[{"field": "organization_name", "message": "No organization is linked to your account"}],
        )

    organization_name = validate_name(payload.organization_name)
    organization = await get_organization_by_id(db, user.org_id)
    if organization is None:
        raise AppException(
            code="ORGANIZATION_NOT_FOUND",
            message="Organization not found",
            status_code=404,
        )

    if await organization_name_exists(
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

    organization.name = organization_name
    await db.commit()
    await db.refresh(organization)
    logger.info("User %s updated organization %s name", user.id, organization.id)
    return organization


async def update_authentication_keys(
    db: AsyncSession,
    user: User,
    payload: AuthKeysRequest,
) -> User:
    """Persist authentication keys in user metadata."""
    key1 = _ensure_non_empty(payload.auth_keys.key1, field="auth_keys.key1", label="Key 1")
    key2 = _ensure_non_empty(payload.auth_keys.key2, field="auth_keys.key2", label="Key 2")

    meta = get_user_meta(user)
    meta[AUTH_KEYS_META_KEY] = {"key1": key1, "key2": key2}
    set_user_meta(user, meta)
    await db.commit()
    await db.refresh(user)
    logger.info("User %s updated authentication keys", user.id)
    return user


def can_enable_push_notifications(user: User) -> bool:
    """Return True when the user is authorized to enable push notifications."""
    return user.role == UserRole.ORG_ADMIN.value or user.is_super_admin


async def update_push_notifications(
    db: AsyncSession,
    user: User,
    payload: PushNotificationsRequest,
) -> User:
    """
    Update push notification preference.

    Raises 400 when enabling without authorization.
    """
    if payload.push_notifications_enabled and not can_enable_push_notifications(user):
        raise AppException(
            code="FORBIDDEN",
            message="You are not authorized to enable push notifications",
            status_code=400,
            details=[
                {
                    "field": "push_notifications_enabled",
                    "message": "You are not authorized to enable push notifications",
                }
            ],
        )

    meta = get_user_meta(user)
    meta[PUSH_NOTIFICATIONS_META_KEY] = payload.push_notifications_enabled
    set_user_meta(user, meta)
    await db.commit()
    await db.refresh(user)
    logger.info(
        "User %s set push_notifications_enabled=%s",
        user.id,
        payload.push_notifications_enabled,
    )
    return user


def build_help_support_payload(user: User) -> dict[str, Any]:
    """Build the help and support screen payload."""
    return {
        "success": True,
        "message": "Help and support loaded successfully",
        "status": "ready",
        "description": "Review help articles and contact support",
        "link": f"{settings.API_V1_PREFIX}/account/settings/help-support/contact",
        "error": None,
        "title": "Help & Support",
        "articles": get_help_articles(),
        "contact": get_support_contact_info(),
        "profile": build_profile_summary(user),
    }


async def update_account_profile(
    db: AsyncSession,
    user: User,
    payload: AccountProfileUpdateRequest,
) -> User:
    """Update profile details from Account Settings using full_name."""
    first_name, last_name = split_full_name(payload.full_name)
    if not last_name:
        last_name = first_name

    profile_payload = CoachProfileUpdateRequest(
        first_name=first_name,
        last_name=last_name,
        email=str(payload.email),
        phone=payload.phone,
    )
    return await profile_service.update_coach_profile(db, user, profile_payload)


async def submit_support_request(
    db: AsyncSession,
    user: User,
    payload: SupportSubmitRequest,
) -> SupportRequest:
    """Create a support request from the Account Settings help screen."""
    try:
        email = str(TypeAdapter(EmailStr).validate_python(str(payload.email))).strip().lower()
    except ValidationError as exc:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Enter a valid email address",
            status_code=400,
            details=[{"field": "email", "message": "Enter a valid email address"}],
        ) from exc

    phone = validate_numeric_phone(payload.phone)
    subject = validate_support_subject(payload.inquiry_subject)
    message = validate_support_message(payload.message_description)

    display_name = profile_service.build_coach_display_name(user)
    support_request = SupportRequest(
        email=email,
        name=display_name,
        subject=subject,
        message=message,
    )
    db.add(support_request)
    await db.commit()
    await db.refresh(support_request)
    logger.info("User %s submitted support request %s", user.id, support_request.id)
    return support_request
