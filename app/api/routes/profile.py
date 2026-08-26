from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_super_admin
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.errors import ErrorResponse
from app.schemas.profile import SuperAdminProfileResponse, SuperAdminProfileUpdateResponse
from app.services import profile as profile_service

router = APIRouter(prefix="/admin/profile", tags=["admin-profile"])


@router.get(
    "",
    response_model=SuperAdminProfileResponse,
    summary="Get super admin profile",
    description=(
        "Returns the authenticated super admin profile including name, email, "
        "and profile image metadata.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid JWT"},
        403: {"model": ErrorResponse, "description": "User is not a super admin"},
    },
)
async def get_super_admin_profile(
    current_user: User = Depends(get_current_super_admin),
) -> SuperAdminProfileResponse:
    return SuperAdminProfileResponse(**profile_service.build_profile_response(current_user))


@router.put(
    "",
    response_model=SuperAdminProfileUpdateResponse,
    summary="Update super admin profile",
    description=(
        "Update the authenticated super admin profile.\n\n"
        "Send as `multipart/form-data`. Password is **not** updated here — "
        "use the forgot/reset password flow instead.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid profile image"},
        401: {"model": ErrorResponse, "description": "Missing or invalid JWT"},
        403: {"model": ErrorResponse, "description": "User is not a super admin"},
        409: {"model": ErrorResponse, "description": "Email already in use"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def update_super_admin_profile(
    name: str | None = Form(default=None, description="Display name"),
    email: EmailStr | None = Form(default=None, description="Email address"),
    profile_image: UploadFile | None = File(
        default=None,
        description="Optional profile image (JPG, JPEG, PNG — max 2 MB)",
    ),
    remove_profile_image: bool = Form(
        default=False,
        description="Set true to remove the current profile image",
    ),
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> SuperAdminProfileUpdateResponse:
    if name is None and email is None and profile_image is None and not remove_profile_image:
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one profile field must be provided",
            status_code=422,
        )

    updated_user = await profile_service.update_super_admin_profile(
        db,
        current_user,
        name=name,
        email=str(email) if email is not None else None,
        profile_image=profile_image,
        remove_profile_image=remove_profile_image,
    )
    profile = SuperAdminProfileResponse(**profile_service.build_profile_response(updated_user))
    return SuperAdminProfileUpdateResponse(
        message="Profile updated successfully.",
        profile=profile,
    )


@router.get(
    "/avatar",
    summary="Get super admin profile avatar",
    description=(
        "Returns the authenticated super admin profile image file.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid JWT"},
        403: {"model": ErrorResponse, "description": "User is not a super admin"},
        404: {"model": ErrorResponse, "description": "Profile image not found"},
    },
)
async def get_super_admin_profile_avatar(
    current_user: User = Depends(get_current_super_admin),
) -> FileResponse:
    image_meta = profile_service.get_profile_image_meta(current_user)
    if image_meta is None or not image_meta.get("path"):
        raise AppException(
            code="PROFILE_IMAGE_NOT_FOUND",
            message="Profile image not found",
            status_code=404,
        )

    from pathlib import Path

    file_path = Path(str(image_meta["path"]))
    if not file_path.is_file():
        raise AppException(
            code="PROFILE_IMAGE_NOT_FOUND",
            message="Profile image file is no longer available",
            status_code=404,
        )

    return FileResponse(
        path=file_path,
        media_type=str(image_meta.get("content_type") or "application/octet-stream"),
        filename=str(image_meta.get("original_name") or file_path.name),
    )
