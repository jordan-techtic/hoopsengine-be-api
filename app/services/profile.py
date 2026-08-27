import logging
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.profile import CoachProfileUpdateRequest
from app.services.organization import validate_phone_number
from app.services.registration import get_user_by_username, validate_username

logger = logging.getLogger(__name__)

PROFILE_IMAGE_META_KEY = "profile_image"
ALLOWED_PROFILE_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def profile_upload_dir() -> Path:
    upload_dir = Path(settings.PROFILE_IMAGE_UPLOAD_DIR)
    if not upload_dir.is_absolute():
        project_root = Path(__file__).resolve().parents[2]
        upload_dir = project_root / upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def get_profile_image_meta(user: User) -> dict[str, Any] | None:
    meta = user.raw_user_meta_data or {}
    image = meta.get(PROFILE_IMAGE_META_KEY)
    if not isinstance(image, dict):
        return None
    if not image.get("path"):
        return None
    return image


def get_display_name(user: User) -> str:
    parts = [user.first_name, user.last_name]
    name = " ".join(part.strip() for part in parts if part and part.strip())
    return name or "Super Admin"


def set_display_name(user: User, name: str) -> None:
    cleaned = name.strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Name is required",
            status_code=422,
        )
    user.first_name = cleaned
    user.last_name = None


def build_profile_image_url() -> str:
    return f"{settings.API_V1_PREFIX}/super-admin/profile/avatar"


def build_profile_response(user: User) -> dict[str, Any]:
    image_meta = get_profile_image_meta(user)
    profile_image = None
    if image_meta is not None:
        profile_image = {
            "url": build_profile_image_url(),
            "original_name": image_meta.get("original_name"),
            "content_type": image_meta.get("content_type"),
        }

    return {
        "id": user.id,
        "name": get_display_name(user),
        "email": user.email,
        "profile_image": profile_image,
        "updated_at": user.updated_at,
    }


async def _email_in_use(
    db: AsyncSession,
    *,
    email: str,
    exclude_user_id: uuid.UUID,
) -> bool:
    result = await db.execute(
        select(User.id).where(
            User.email == email,
            User.id != exclude_user_id,
            User.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none() is not None


def _delete_stored_image(image_meta: dict[str, Any] | None) -> None:
    if image_meta is None:
        return
    file_path = image_meta.get("path")
    if not file_path:
        return
    path = Path(str(file_path))
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            logger.exception("Failed to delete profile image at %s", path)


async def save_profile_image(user: User, upload: UploadFile) -> dict[str, Any]:
    filename = upload.filename or ""
    if not filename:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Profile image file is required when uploading",
            status_code=422,
        )

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_PROFILE_IMAGE_EXTENSIONS:
        raise AppException(
            code="INVALID_PROFILE_IMAGE_TYPE",
            message="Unsupported profile image type. Allowed files: JPG, JPEG, PNG.",
            status_code=400,
        )

    content = await upload.read()
    max_size = settings.PROFILE_IMAGE_MAX_SIZE_MB * 1024 * 1024
    if len(content) > max_size:
        raise AppException(
            code="PROFILE_IMAGE_TOO_LARGE",
            message=f"Profile image size must be {settings.PROFILE_IMAGE_MAX_SIZE_MB} MB or less",
            status_code=400,
        )

    stored_name = f"{uuid.uuid4()}{suffix}"
    file_path = profile_upload_dir() / stored_name
    file_path.write_bytes(content)

    return {
        "original_name": Path(filename).name,
        "stored_name": stored_name,
        "path": str(file_path),
        "content_type": upload.content_type or "application/octet-stream",
        "size_bytes": len(content),
    }


async def update_super_admin_profile(
    db: AsyncSession,
    user: User,
    *,
    name: str | None = None,
    email: str | None = None,
    profile_image: UploadFile | None = None,
    remove_profile_image: bool = False,
) -> User:
    if name is not None:
        set_display_name(user, name)

    if email is not None:
        normalized_email = email.strip().lower()
        if normalized_email != user.email.lower():
            if await _email_in_use(db, email=normalized_email, exclude_user_id=user.id):
                raise AppException(
                    code="EMAIL_ALREADY_IN_USE",
                    message="This email is already in use by another account",
                    status_code=409,
                )
            user.email = normalized_email

    meta = dict(user.raw_user_meta_data or {})
    current_image = get_profile_image_meta(user)

    if remove_profile_image:
        _delete_stored_image(current_image)
        meta.pop(PROFILE_IMAGE_META_KEY, None)
    elif profile_image is not None and profile_image.filename:
        new_image = await save_profile_image(user, profile_image)
        _delete_stored_image(current_image)
        meta[PROFILE_IMAGE_META_KEY] = new_image

    user.raw_user_meta_data = meta or None
    await db.commit()
    await db.refresh(user)
    return user


DATE_OF_BIRTH_FORMAT = "%m/%d/%Y"
_email_adapter = TypeAdapter(EmailStr)


def _require_non_empty(value: str, field: str) -> str:
    """Return trimmed text or raise 400 when a required profile field is empty."""
    cleaned = value.strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message=f"{field.replace('_', ' ').title()} is required",
            status_code=400,
            details=[{"field": field, "message": f"{field.replace('_', ' ').title()} is required"}],
        )
    return cleaned


def validate_profile_email(email: str) -> str:
    """Validate and normalize an email address."""
    cleaned = _require_non_empty(email, "email")
    try:
        normalized = str(_email_adapter.validate_python(cleaned)).strip().lower()
    except ValidationError as exc:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Enter a valid email address",
            status_code=400,
            details=[{"field": "email", "message": "Enter a valid email address"}],
        ) from exc
    return normalized


def parse_date_of_birth(value: str | None) -> date | None:
    """Parse MM/DD/YYYY date of birth or raise 400 when invalid."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return datetime.strptime(cleaned, DATE_OF_BIRTH_FORMAT).date()
    except ValueError as exc:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Date of birth must use MM/DD/YYYY format",
            status_code=400,
            details=[
                {
                    "field": "date_of_birth",
                    "message": "Date of birth must use MM/DD/YYYY format",
                }
            ],
        ) from exc


def format_date_of_birth(value: date | None) -> str | None:
    """Format a stored date of birth for the mobile client."""
    if value is None:
        return None
    return value.strftime(DATE_OF_BIRTH_FORMAT)


def build_coach_display_name(user: User) -> str:
    """Return the full display name for profile responses."""
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(part.strip() for part in parts if part and part.strip()).strip()
    return name or (user.username or "User")


def build_coach_avatar(user: User) -> dict[str, Any] | None:
    """Return avatar metadata when a profile image is stored."""
    image_meta = get_profile_image_meta(user)
    if image_meta is None:
        return None
    return {
        "url": None,
        "original_name": image_meta.get("original_name"),
        "content_type": image_meta.get("content_type"),
    }


def build_coach_profile_data(user: User) -> dict[str, Any]:
    """Build nested profile payload for coach edit profile responses."""
    phone_number = user.phone
    return {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "username": user.username,
        "phone_number": phone_number,
        "date_of_birth": format_date_of_birth(user.date_of_birth),
        "gender": user.gender,
        "grade": user.grade,
        "parent_guardian": user.parent_guardian,
    }


def build_coach_profile_response(
    user: User,
    *,
    message: str,
    description: str,
    status: str = "ready",
) -> dict[str, Any]:
    """Map a user row to the coach edit profile API envelope."""
    profile_data = build_coach_profile_data(user)
    phone_number = user.phone
    return {
        "success": True,
        "message": message,
        "status": status,
        "description": description,
        "link": None,
        "error": None,
        "title": "Edit Profile",
        "id": user.id,
        "name": build_coach_display_name(user),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "username": user.username,
        "phone_number": phone_number,
        "phone": phone_number,
        "date_of_birth": profile_data["date_of_birth"],
        "gender": user.gender,
        "grade": user.grade,
        "parent_guardian": user.parent_guardian,
        "address": None,
        "avatar": build_coach_avatar(user),
        "profile": profile_data,
    }


async def _username_in_use(
    db: AsyncSession,
    *,
    username: str,
    exclude_user_id: uuid.UUID,
) -> bool:
    existing = await get_user_by_username(db, username)
    return existing is not None and existing.id != exclude_user_id


async def update_coach_profile(
    db: AsyncSession,
    user: User,
    payload: CoachProfileUpdateRequest,
) -> User:
    """Update the authenticated user's coach profile fields."""
    first_name = _require_non_empty(payload.first_name, "first_name")
    last_name = _require_non_empty(payload.last_name, "last_name")
    email = validate_profile_email(payload.email)

    if len(first_name) > 50:
        raise AppException(
            code="VALIDATION_ERROR",
            message="First name must be at most 50 characters",
            status_code=400,
            details=[{"field": "first_name", "message": "First name must be at most 50 characters"}],
        )
    if len(last_name) > 50:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Last name must be at most 50 characters",
            status_code=400,
            details=[{"field": "last_name", "message": "Last name must be at most 50 characters"}],
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

    if payload.username is not None:
        normalized_username = validate_username(payload.username)
        if normalized_username != (user.username or ""):
            if await _username_in_use(db, username=normalized_username, exclude_user_id=user.id):
                raise AppException(
                    code="USERNAME_ALREADY_IN_USE",
                    message="This username is already in use by another account",
                    status_code=409,
                    details=[
                        {
                            "field": "username",
                            "message": "This username is already in use by another account",
                        }
                    ],
                )
            user.username = normalized_username

    if payload.phone_number is not None:
        cleaned_phone = payload.phone_number.strip()
        user.phone = validate_phone_number(cleaned_phone) if cleaned_phone else None

    user.first_name = first_name
    user.last_name = last_name
    user.date_of_birth = parse_date_of_birth(payload.date_of_birth)
    user.gender = payload.gender.strip() if payload.gender and payload.gender.strip() else None
    user.grade = payload.grade.strip() if payload.grade and payload.grade.strip() else None
    user.parent_guardian = (
        payload.parent_guardian.strip()
        if payload.parent_guardian and payload.parent_guardian.strip()
        else None
    )

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError as exc:
        await db.rollback()
        logger.warning("Profile update failed for user %s: %s", user.id, exc)
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
        ) from exc

    logger.info("Updated profile for user %s", user.id)
    return user
