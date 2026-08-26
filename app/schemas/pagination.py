from pydantic import BaseModel, ConfigDict, Field


class PaginationMeta(BaseModel):
    """Pagination metadata shared by Super Admin list endpoints."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "page": 1,
                "page_size": 20,
                "total": 42,
                "total_pages": 3,
                "has_next": True,
                "has_prev": False,
            }
        }
    )

    page: int = Field(description="Current page number (1-based)", examples=[1])
    page_size: int = Field(description="Number of items per page", examples=[20])
    total: int = Field(description="Total number of matching items", examples=[42])
    total_pages: int = Field(description="Total number of pages", examples=[3])
    has_next: bool = Field(description="Whether a next page exists", examples=[True])
    has_prev: bool = Field(description="Whether a previous page exists", examples=[False])
