from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class ProfileImageResponse(BaseModel):
    url: str | None = None
    original_name: str | None = None
    content_type: str | None = None


class SuperAdminProfileResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "a752feb1-7852-4a3e-9d07-2628b9873cb1",
                "name": "Super Admin",
                "email": "admin.hoopsengine@yopmail.com",
                "profile_image": {
                    "url": "/api/v1/admin/profile/avatar",
                    "original_name": "avatar.png",
                    "content_type": "image/png",
                },
                "updated_at": "2026-08-19T10:00:00.000000Z",
            }
        }
    )

    id: UUID
    name: str
    email: EmailStr
    profile_image: ProfileImageResponse | None = None
    updated_at: datetime


class SuperAdminProfileUpdateResponse(BaseModel):
    message: str
    profile: SuperAdminProfileResponse
