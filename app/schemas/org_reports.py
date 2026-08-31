"""Pydantic schemas for organization admin reports API (HE-449)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

REPORT_CRITERIA_EXAMPLE = {
    "date_range": "2023-01-01 to 2023-12-31",
    "user_segments": ["segment1", "segment2"],
}

REPORT_GENERATE_REQUEST_EXAMPLE = {
    "criteria": REPORT_CRITERIA_EXAMPLE,
}

REPORT_METRICS_EXAMPLE = {
    "total_coaches": 5,
    "total_players": 20,
    "total_sessions": 12,
    "total_makes": 150,
    "total_attempts": 300,
    "shooting_percent": 50,
}


class ReportCriteria(BaseModel):
    """Filter criteria for report generation."""

    model_config = ConfigDict(json_schema_extra={"example": REPORT_CRITERIA_EXAMPLE})

    date_range: str | None = Field(
        default=None,
        description="Inclusive date range as 'YYYY-MM-DD to YYYY-MM-DD'",
        examples=["2023-01-01 to 2023-12-31"],
    )
    date_start: date | None = Field(
        default=None,
        description="Alternative start date when date_range is omitted",
        examples=["2023-01-01"],
    )
    date_end: date | None = Field(
        default=None,
        description="Alternative end date when date_range is omitted",
        examples=["2023-12-31"],
    )
    user_segments: list[str] | None = Field(
        default=None,
        description="Optional audience segments (e.g. coach, player, segment1)",
        examples=[["segment1", "segment2"]],
    )

    @field_validator("date_range")
    @classmethod
    def strip_date_range(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("user_segments")
    @classmethod
    def normalize_segments(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [segment.strip() for segment in value if segment and segment.strip()]
        return cleaned or None


class ReportGenerateRequest(BaseModel):
    """Payload for POST /reports/generate."""

    model_config = ConfigDict(json_schema_extra={"example": REPORT_GENERATE_REQUEST_EXAMPLE})

    criteria: ReportCriteria = Field(description="Report generation criteria")


class ReportMetrics(BaseModel):
    """Performance metrics included in a generated report."""

    model_config = ConfigDict(json_schema_extra={"example": REPORT_METRICS_EXAMPLE})

    total_coaches: int = Field(ge=0, description="Coach count in scope")
    total_players: int = Field(ge=0, description="Player count in scope")
    total_sessions: int = Field(ge=0, description="Practice session count in scope")
    total_makes: int = Field(ge=0, description="Aggregate field-goal makes")
    total_attempts: int = Field(ge=0, description="Aggregate field-goal attempts")
    shooting_percent: int = Field(ge=0, le=100, description="Integer shooting percentage")


class ReportGenerateResponse(BaseModel):
    """Successful report generation response."""

    success: bool = Field(default=True, description="Always true on success")
    message: str = Field(description="Human-readable outcome message")
    report_id: UUID = Field(description="Generated report identifier")
    data: ReportMetrics = Field(description="Report performance metrics")
    criteria: ReportCriteria = Field(description="Criteria used to build the report")
    error: None = Field(default=None, description="Always null on success")


class ReportDetailResponse(BaseModel):
    """Report details returned by GET /reports/{report_id}."""

    success: bool = Field(default=True)
    message: str | None = Field(default=None, description="Optional status message")
    report_id: UUID = Field(description="Report identifier")
    criteria: ReportCriteria = Field(description="Criteria used for generation")
    data: ReportMetrics = Field(description="Report performance metrics")
    generated_at: datetime = Field(description="UTC timestamp when the report was created")
    error: None = Field(default=None)


class ReportExportRequest(BaseModel):
    """Payload for POST /reports/export."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "report_id": "11111111-2222-3333-4444-555555555555",
                "format": "csv",
            }
        }
    )

    report_id: UUID = Field(description="Report to export")
    format: Literal["csv", "pdf"] = Field(description="Export format: csv or pdf")

    @field_validator("format", mode="before")
    @classmethod
    def normalize_format(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class ReportExportResponse(BaseModel):
    """Successful export response."""

    success: bool = Field(default=True)
    message: str = Field(description="Export success message")
    format: Literal["csv", "pdf"] = Field(description="Exported format")
    content_base64: str = Field(description="Base64-encoded export file contents")
    filename: str = Field(description="Suggested download filename")
    error: None = Field(default=None)


class ParsedReportCriteria(BaseModel):
    """Normalized criteria used internally by the report service."""

    date_start: date
    date_end: date
    user_segments: list[str] | None = None

    @model_validator(mode="after")
    def validate_range(self) -> ParsedReportCriteria:
        if self.date_end < self.date_start:
            raise ValueError("date_end must be on or after date_start")
        return self
