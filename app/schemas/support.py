import math
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas.pagination import PaginationMeta


class SupportAttachmentResponse(BaseModel):
    original_name: str
    content_type: str | None = None
    size_bytes: int
    download_url: str


class SupportRequestCreateResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Your support request has been submitted successfully.",
                "request_id": "11111111-2222-3333-4444-555555555555",
            }
        }
    )

    message: str
    request_id: UUID


class SupportRequestItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    name: str
    subject: str
    message: str
    created_at: datetime
    attachment: SupportAttachmentResponse | None = None


def build_pagination_meta(total: int, page: int, page_size: int) -> PaginationMeta:
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginationMeta(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1 and total_pages > 0,
    )


class SupportRequestListResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "11111111-2222-3333-4444-555555555555",
                        "email": "user@example.com",
                        "name": "John Doe",
                        "subject": "Unable to login",
                        "message": "I am not able to log in to the app.",
                        "created_at": "2026-08-17T08:30:00.000000Z",
                        "attachment": {
                            "original_name": "screenshot.png",
                            "content_type": "image/png",
                            "size_bytes": 245812,
                            "download_url": "/api/v1/support-requests/11111111-2222-3333-4444-555555555555/attachment",
                        },
                    }
                ],
                "pagination": {
                    "page": 1,
                    "page_size": 20,
                    "total": 1,
                    "total_pages": 1,
                    "has_next": False,
                    "has_prev": False,
                },
            }
        }
    )

    items: list[SupportRequestItem]
    pagination: PaginationMeta
