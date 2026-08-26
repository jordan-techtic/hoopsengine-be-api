import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.models.user import User

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
