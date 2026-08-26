from pydantic import BaseModel, ConfigDict, Field


class PaginationMeta(BaseModel):
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

    page: int = Field(description="Current page number (1-based)")
    page_size: int = Field(description="Number of items per page")
    total: int = Field(description="Total number of matching items")
    total_pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether a next page exists")
    has_prev: bool = Field(description="Whether a previous page exists")
