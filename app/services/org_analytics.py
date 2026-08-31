"""Business logic for organization admin analytics (HE-452)."""

from __future__ import annotations

import base64
import csv
import io
import logging
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.org_analytics import (
    AnalyticsDashboardResponse,
    AnalyticsExportResponse,
    AnalyticsFilters,
    AnalyticsMetrics,
)
from app.schemas.org_reports import ReportCriteria, ReportMetrics
from app.services import org_reports as org_reports_service

logger = logging.getLogger(__name__)

DEFAULT_DASHBOARD_FILTERS = AnalyticsFilters(
    date_range="2000-01-01 to 2099-12-31",
    user_segments=None,
)
EMPTY_ANALYTICS_MESSAGE = "No analytics data is available for the selected criteria."
DASHBOARD_SUCCESS_MESSAGE = "Analytics dashboard loaded successfully."
FILTER_SUCCESS_MESSAGE = "Analytics filters applied successfully."
EXPORT_SUCCESS_MESSAGE = "Analytics insights exported successfully."
SUPPORTED_EXPORT_FORMATS = frozenset({"csv", "pdf"})


def _filters_to_criteria(filters: AnalyticsFilters) -> ReportCriteria:
    """Map analytics filters to shared report criteria."""
    return ReportCriteria.model_validate(filters.model_dump(mode="json"))


def _build_insights(metrics: ReportMetrics) -> list[str]:
    """Derive human-readable insights from analytics metrics."""
    insights: list[str] = []
    if metrics.total_sessions > 0:
        insights.append(
            f"Organization recorded {metrics.total_sessions} practice sessions in the selected period."
        )
    if metrics.total_players > 0:
        insights.append(f"{metrics.total_players} players are active in scope.")
    if metrics.total_coaches > 0:
        insights.append(f"{metrics.total_coaches} coaches are active in scope.")
    if metrics.total_attempts > 0:
        insights.append(
            f"Players attempted {metrics.total_attempts} field goals with "
            f"{metrics.shooting_percent}% shooting."
        )
    if not insights:
        insights.append("No significant trends identified for the selected period.")
    return insights


def _build_dashboard_response(
    metrics: AnalyticsMetrics,
    filters: AnalyticsFilters,
    *,
    message: str,
) -> AnalyticsDashboardResponse:
    """Build a successful analytics dashboard response."""
    return AnalyticsDashboardResponse(
        message=message,
        data=metrics,
        filters=filters,
        insights=_build_insights(metrics),
    )


async def _load_metrics(
    db: AsyncSession,
    user: User,
    filters: AnalyticsFilters,
) -> AnalyticsMetrics:
    """Load org-scoped metrics for the given filters."""
    org_id = await org_reports_service.require_org_id(user)
    parsed = org_reports_service.parse_report_criteria(_filters_to_criteria(filters))
    metrics = await org_reports_service.build_org_metrics(db, org_id, parsed)
    return AnalyticsMetrics.model_validate(metrics.model_dump(mode="json"))


def _raise_when_empty(metrics: AnalyticsMetrics) -> None:
    """Raise 404 when no analytics data exists for the criteria."""
    if org_reports_service._metrics_are_empty(metrics):
        raise AppException(
            code="ANALYTICS_NOT_FOUND",
            message=EMPTY_ANALYTICS_MESSAGE,
            status_code=404,
        )


async def get_analytics_dashboard(
    db: AsyncSession,
    user: User,
) -> AnalyticsDashboardResponse:
    """Return default analytics dashboard data for the authenticated org admin."""
    metrics = await _load_metrics(db, user, DEFAULT_DASHBOARD_FILTERS)
    _raise_when_empty(metrics)
    logger.info("Loaded analytics dashboard for org admin %s", user.id)
    return _build_dashboard_response(
        metrics,
        DEFAULT_DASHBOARD_FILTERS,
        message=DASHBOARD_SUCCESS_MESSAGE,
    )


async def filter_analytics(
    db: AsyncSession,
    user: User,
    filters: AnalyticsFilters,
) -> AnalyticsDashboardResponse:
    """Apply filters and return analytics metrics for the org admin."""
    metrics = await _load_metrics(db, user, filters)
    message = (
        EMPTY_ANALYTICS_MESSAGE
        if org_reports_service._metrics_are_empty(metrics)
        else FILTER_SUCCESS_MESSAGE
    )
    logger.info("Applied analytics filters for org admin %s", user.id)
    return _build_dashboard_response(metrics, filters, message=message)


def _escape_pdf_text(value: str) -> str:
    """Escape parentheses and backslashes for PDF literal strings."""
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_csv_content(
    metrics: AnalyticsMetrics,
    filters: AnalyticsFilters,
    export_id: UUID,
) -> bytes:
    """Build CSV export bytes for analytics insights."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["metric", "value"])
    writer.writerow(["export_id", str(export_id)])
    writer.writerow(["date_range", filters.date_range or ""])
    writer.writerow(["total_coaches", metrics.total_coaches])
    writer.writerow(["total_players", metrics.total_players])
    writer.writerow(["total_sessions", metrics.total_sessions])
    writer.writerow(["total_makes", metrics.total_makes])
    writer.writerow(["total_attempts", metrics.total_attempts])
    writer.writerow(["shooting_percent", metrics.shooting_percent])
    for index, insight in enumerate(_build_insights(metrics), start=1):
        writer.writerow([f"insight_{index}", insight])
    return buffer.getvalue().encode("utf-8")


def _build_pdf_content(
    metrics: AnalyticsMetrics,
    filters: AnalyticsFilters,
    export_id: UUID,
) -> bytes:
    """Build a minimal valid PDF document for analytics insights."""
    lines = [
        f"Analytics Export: {export_id}",
        f"Date Range: {filters.date_range or 'n/a'}",
        f"Coaches: {metrics.total_coaches}",
        f"Players: {metrics.total_players}",
        f"Sessions: {metrics.total_sessions}",
        f"Makes: {metrics.total_makes}",
        f"Attempts: {metrics.total_attempts}",
        f"Shooting %: {metrics.shooting_percent}",
    ]
    lines.extend(_build_insights(metrics))
    content_lines = ["BT", "/F1 12 Tf", "50 750 Td", "14 TL"]
    for index, line in enumerate(lines):
        prefix = "" if index == 0 else "T* "
        content_lines.append(f"{prefix}({_escape_pdf_text(line)}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")
    stream_header = f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
    stream_footer = b"\nendstream"

    objects: list[bytes] = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objects.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    )
    objects.append(b"4 0 obj\n" + stream_header + stream + stream_footer + b"\nendobj\n")
    objects.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    pdf = io.BytesIO()
    pdf.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(pdf.tell())
        pdf.write(obj)
    xref_start = pdf.tell()
    pdf.write(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.write(
        (
            f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF"
        ).encode("ascii")
    )
    return pdf.getvalue()


async def export_analytics(
    db: AsyncSession,
    user: User,
    filters: AnalyticsFilters,
    export_format: str,
) -> AnalyticsExportResponse:
    """Export analytics insights for the supplied filters."""
    normalized_format = export_format.strip().lower()
    if normalized_format not in SUPPORTED_EXPORT_FORMATS:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Export format must be csv or pdf",
            status_code=400,
            details=[{"field": "format", "message": "Supported formats: csv, pdf"}],
        )

    metrics = await _load_metrics(db, user, filters)
    export_id = uuid4()
    try:
        if normalized_format == "csv":
            content = _build_csv_content(metrics, filters, export_id)
        else:
            content = _build_pdf_content(metrics, filters, export_id)
    except Exception as exc:
        logger.exception("Failed to export analytics as %s", normalized_format)
        raise AppException(
            code="EXPORT_FAILED",
            message="Unable to load analytics data due to a network or processing error",
            status_code=502,
        ) from exc

    encoded = base64.b64encode(content).decode("ascii")
    extension = "csv" if normalized_format == "csv" else "pdf"
    logger.info("Exported analytics insights as %s for org admin %s", normalized_format, user.id)
    return AnalyticsExportResponse(
        message=EXPORT_SUCCESS_MESSAGE,
        format=normalized_format,  # type: ignore[arg-type]
        content_base64=encoded,
        filename=f"analytics-{export_id}.{extension}",
    )
