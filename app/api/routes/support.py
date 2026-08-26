import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import EmailStr
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_super_admin
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.support_request import SupportRequest
from app.models.user import User
from app.schemas.errors import ErrorResponse
from app.schemas.support import (
    SupportAttachmentResponse,
    SupportRequestCreateResponse,
    SupportRequestItem,
    SupportRequestListResponse,
    build_pagination_meta,
)

router = APIRouter(prefix="/support-requests", tags=["support"])

ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".txt",
}


def _support_upload_dir() -> Path:
    upload_dir = Path(settings.SUPPORT_REQUEST_UPLOAD_DIR)
    if not upload_dir.is_absolute():
        project_root = Path(__file__).resolve().parents[3]
        upload_dir = project_root / upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _require_non_empty(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message=f"{field_name} is required",
            status_code=422,
        )
    return cleaned


async def _save_attachment(attachment: UploadFile) -> dict[str, str | int] | None:
    filename = attachment.filename or ""
    if not filename:
        return None

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise AppException(
            code="INVALID_ATTACHMENT_TYPE",
            message=(
                "Unsupported attachment type. Allowed files: JPG, JPEG, PNG, WEBP, "
                "PDF, DOC, DOCX, XLS, XLSX, TXT."
            ),
            status_code=400,
        )

    content = await attachment.read()
    max_size = settings.SUPPORT_REQUEST_MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
    if len(content) > max_size:
        raise AppException(
            code="ATTACHMENT_TOO_LARGE",
            message=f"Attachment size must be {settings.SUPPORT_REQUEST_MAX_ATTACHMENT_SIZE_MB} MB or less",
            status_code=400,
        )

    stored_name = f"{uuid.uuid4()}{suffix}"
    upload_dir = _support_upload_dir()
    file_path = upload_dir / stored_name
    file_path.write_bytes(content)

    return {
        "original_name": Path(filename).name,
        "stored_name": stored_name,
        "path": str(file_path),
        "content_type": attachment.content_type or "application/octet-stream",
        "size_bytes": len(content),
    }


def _attachment_download_url(request_id: UUID) -> str:
    return f"{settings.API_V1_PREFIX}/support-requests/{request_id}/attachment"


def _build_search_filter(search: str | None) -> list:
    if search is None:
        return []

    term = search.strip()
    if not term:
        return []

    pattern = f"%{term}%"
    return [
        or_(
            SupportRequest.email.ilike(pattern),
            SupportRequest.name.ilike(pattern),
            SupportRequest.subject.ilike(pattern),
            SupportRequest.message.ilike(pattern),
        )
    ]


def _to_item(support_request: SupportRequest) -> SupportRequestItem:
    attachment = None
    if support_request.attachment_original_name and support_request.attachment_size_bytes is not None:
        attachment = SupportAttachmentResponse(
            original_name=support_request.attachment_original_name,
            content_type=support_request.attachment_content_type,
            size_bytes=support_request.attachment_size_bytes,
            download_url=_attachment_download_url(support_request.id),
        )

    return SupportRequestItem(
        id=support_request.id,
        email=support_request.email,
        name=support_request.name,
        subject=support_request.subject,
        message=support_request.message,
        created_at=support_request.created_at,
        attachment=attachment,
    )


@router.post(
    "",
    response_model=SupportRequestCreateResponse,
    summary="Create support request",
    description=(
        "Submit a support request using `multipart/form-data`.\n\n"
        "**Allowed attachments:** JPG, JPEG, PNG, WEBP, PDF, DOC, DOCX, XLS, XLSX, TXT "
        "(max 5 MB). Attachment is optional."
    ),
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Invalid attachment type or file too large",
        },
        422: {
            "model": ErrorResponse,
            "description": "Validation error (missing or invalid fields)",
        },
    },
)
async def create_support_request(
    email: EmailStr = Form(..., description="Contact email address", examples=["user@example.com"]),
    name: str = Form(..., description="Full name", examples=["John Doe"]),
    subject: str = Form(..., description="Subject of the support request", examples=["Unable to login"]),
    message: str = Form(
        ...,
        description="Detailed message describing the issue",
        examples=["I am not able to log in to the app."],
    ),
    attachment: UploadFile | None = File(
        default=None,
        description=(
            "Optional file attachment. Allowed: JPG, JPEG, PNG, WEBP, PDF, DOC, DOCX, "
            "XLS, XLSX, TXT (max 5 MB)."
        ),
    ),
    db: AsyncSession = Depends(get_db),
) -> SupportRequestCreateResponse:
    clean_name = _require_non_empty(name, "Name")
    clean_subject = _require_non_empty(subject, "Subject")
    clean_message = _require_non_empty(message, "Message")

    attachment_data = None
    if attachment is not None:
        attachment_data = await _save_attachment(attachment)

    support_request = SupportRequest(
        email=str(email).strip(),
        name=clean_name,
        subject=clean_subject,
        message=clean_message,
        attachment_original_name=(
            str(attachment_data["original_name"]) if attachment_data is not None else None
        ),
        attachment_stored_name=(
            str(attachment_data["stored_name"]) if attachment_data is not None else None
        ),
        attachment_path=str(attachment_data["path"]) if attachment_data is not None else None,
        attachment_content_type=(
            str(attachment_data["content_type"]) if attachment_data is not None else None
        ),
        attachment_size_bytes=(
            int(attachment_data["size_bytes"]) if attachment_data is not None else None
        ),
    )
    db.add(support_request)
    await db.commit()
    await db.refresh(support_request)

    return SupportRequestCreateResponse(
        message="Your support request has been submitted successfully.",
        request_id=support_request.id,
    )


@router.get(
    "",
    response_model=SupportRequestListResponse,
    summary="Get support requests",
    description=(
        "Fetch submitted support requests with pagination and search, newest first.\n\n"
        "Use `search` to filter by email, name, subject, or message (case-insensitive).\n\n"
        "**Requires super admin JWT** — authorize via **Authorize** in Swagger UI."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid JWT"},
        403: {"model": ErrorResponse, "description": "User is not a super admin"},
    },
)
async def list_support_requests(
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of items per page (1–100)",
    ),
    search: str | None = Query(
        default=None,
        description="Search by email, name, subject, or message (case-insensitive)",
        examples=["login", "john@example.com"],
    ),
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> SupportRequestListResponse:
    filters = _build_search_filter(search)
    total_query = select(func.count()).select_from(SupportRequest)
    if filters:
        total_query = total_query.where(*filters)

    total = await db.scalar(total_query) or 0
    offset = (page - 1) * page_size

    list_query = select(SupportRequest).order_by(SupportRequest.created_at.desc())
    if filters:
        list_query = list_query.where(*filters)

    result = await db.execute(list_query.offset(offset).limit(page_size))
    items = [_to_item(item) for item in result.scalars().all()]
    return SupportRequestListResponse(
        items=items,
        pagination=build_pagination_meta(total=total, page=page, page_size=page_size),
    )


@router.get(
    "/{request_id}/attachment",
    summary="Download support request attachment",
    description=(
        "Download the attachment for a support request.\n\n"
        "Returns the original file with a `Content-Disposition` header so the browser "
        "can save it using the original filename.\n\n"
        "**Requires super admin JWT** — authorize via **Authorize** in Swagger UI."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid JWT"},
        403: {"model": ErrorResponse, "description": "User is not a super admin"},
        404: {"model": ErrorResponse, "description": "Support request or attachment not found"},
    },
)
async def download_support_request_attachment(
    request_id: UUID,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    result = await db.execute(
        select(SupportRequest).where(SupportRequest.id == request_id)
    )
    support_request = result.scalar_one_or_none()
    if support_request is None:
        raise AppException(
            code="SUPPORT_REQUEST_NOT_FOUND",
            message="Support request not found",
            status_code=404,
        )

    if not support_request.attachment_path or not support_request.attachment_original_name:
        raise AppException(
            code="ATTACHMENT_NOT_FOUND",
            message="No attachment found for this support request",
            status_code=404,
        )

    file_path = Path(support_request.attachment_path)
    if not file_path.is_file():
        raise AppException(
            code="ATTACHMENT_NOT_FOUND",
            message="Attachment file is no longer available",
            status_code=404,
        )

    return FileResponse(
        path=file_path,
        media_type=support_request.attachment_content_type or "application/octet-stream",
        filename=support_request.attachment_original_name,
    )
