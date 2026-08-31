"""Business logic for organization admin reports (HE-449)."""

from __future__ import annotations

import base64
import csv
import io
import logging
import re
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.enums import UserRole
from app.models.org_report import OrgReport
from app.models.user import User
from app.schemas.org_reports import (
    ParsedReportCriteria,
    ReportCriteria,
    ReportDetailResponse,
    ReportExportResponse,
    ReportGenerateResponse,
    ReportMetrics,
)
from app.services import client_db
from app.services.session_summary import FREE_THROW_CATEGORY_PATTERN, compute_shooting_percent

logger = logging.getLogger(__name__)

DATE_RANGE_PATTERN = re.compile(
    r"^(?P<start>\d{4}-\d{2}-\d{2})\s+to\s+(?P<end>\d{4}-\d{2}-\d{2})$"
)
EMPTY_REPORT_MESSAGE = "No reports are available for the selected criteria."
GENERATED_REPORT_MESSAGE = "Report generated successfully."
EXPORT_SUCCESS_MESSAGE = "Report exported successfully."
PRACTICE_SESSIONS_TABLE = "practice_sessions"
SESSION_DATA_TABLE = "session_data"
PLAYERS_TABLE = "players"

SUPPORTED_EXPORT_FORMATS = frozenset({"csv", "pdf"})


def _parse_iso_date(value: str, field_name: str) -> date:
    """Parse YYYY-MM-DD or raise AppException 400."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Enter a valid date range",
            status_code=400,
            details=[{"field": field_name, "message": "Date must use YYYY-MM-DD format"}],
        ) from exc


def parse_report_criteria(criteria: ReportCriteria) -> ParsedReportCriteria:
    """Validate and normalize report criteria from the API payload."""
    date_start: date | None = criteria.date_start
    date_end: date | None = criteria.date_end

    if criteria.date_range:
        match = DATE_RANGE_PATTERN.match(criteria.date_range.strip())
        if match is None:
            raise AppException(
                code="VALIDATION_ERROR",
                message="Enter a valid date range",
                status_code=400,
                details=[
                    {
                        "field": "criteria.date_range",
                        "message": "Date range must use the format YYYY-MM-DD to YYYY-MM-DD",
                    }
                ],
            )
        date_start = _parse_iso_date(match.group("start"), "criteria.date_range")
        date_end = _parse_iso_date(match.group("end"), "criteria.date_range")

    if date_start is None or date_end is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="A valid date range is required",
            status_code=400,
            details=[
                {
                    "field": "criteria.date_range",
                    "message": "Provide date_range or both date_start and date_end",
                }
            ],
        )

    if date_end < date_start:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Enter a valid date range",
            status_code=400,
            details=[
                {
                    "field": "criteria.date_range",
                    "message": "End date must be on or after start date",
                }
            ],
        )

    try:
        return ParsedReportCriteria(
            date_start=date_start,
            date_end=date_end,
            user_segments=criteria.user_segments,
        )
    except ValueError as exc:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Enter a valid date range",
            status_code=400,
            details=[{"field": "criteria.date_range", "message": str(exc)}],
        ) from exc


def _segment_includes_coaches(segments: list[str] | None) -> bool:
    """Return True when segments do not restrict coaches out of scope."""
    if not segments:
        return True
    normalized = {segment.strip().lower() for segment in segments}
    if normalized & {"coach", "coaches"}:
        return True
    if normalized & {"player", "players"} and "coach" not in normalized and "coaches" not in normalized:
        return False
    return True


def _segment_includes_players(segments: list[str] | None) -> bool:
    """Return True when segments do not restrict players out of scope."""
    if not segments:
        return True
    normalized = {segment.strip().lower() for segment in segments}
    if normalized & {"player", "players"}:
        return True
    if normalized & {"coach", "coaches"} and "player" not in normalized and "players" not in normalized:
        return False
    return True


async def _count_users_for_org(
    db: AsyncSession,
    org_id: UUID,
    role: str,
) -> int:
    """Count non-deleted users with a role scoped to an organization."""
    result = await db.execute(
        select(func.count())
        .select_from(User)
        .where(
            User.org_id == org_id,
            User.role == role,
            User.deleted_at.is_(None),
        )
    )
    return int(result.scalar() or 0)


async def _count_sessions_for_org(
    db: AsyncSession,
    org_id: UUID,
    parsed: ParsedReportCriteria,
) -> int:
    """Count practice sessions for an organization within the date range."""
    if not await client_db.table_exists(db, PRACTICE_SESSIONS_TABLE):
        return 0

    result = await db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM practice_sessions
            WHERE org_id = :org_id
              AND COALESCE(started_at, created_at)::date >= :date_start
              AND COALESCE(started_at, created_at)::date <= :date_end
            """
        ),
        {
            "org_id": org_id,
            "date_start": parsed.date_start,
            "date_end": parsed.date_end,
        },
    )
    return int(result.scalar() or 0)


async def _aggregate_shooting_stats(
    db: AsyncSession,
    org_id: UUID,
    parsed: ParsedReportCriteria,
) -> tuple[int, int]:
    """Return aggregate makes and attempts for org players in the date range."""
    if not await client_db.table_exists(db, SESSION_DATA_TABLE):
        return 0, 0
    if not await client_db.table_exists(db, PLAYERS_TABLE):
        return 0, 0
    if not await client_db.table_exists(db, PRACTICE_SESSIONS_TABLE):
        return 0, 0

    result = await db.execute(
        text(
            """
            SELECT
                COALESCE(
                    SUM(
                        CASE
                            WHEN d.category IS NOT NULL
                                 AND LOWER(d.category) LIKE :free_throw_pattern
                            THEN 0
                            ELSE sd.makes
                        END
                    ),
                    0
                ) AS makes,
                COALESCE(
                    SUM(
                        CASE
                            WHEN d.category IS NOT NULL
                                 AND LOWER(d.category) LIKE :free_throw_pattern
                            THEN 0
                            ELSE sd.attempts
                        END
                    ),
                    0
                ) AS attempts
            FROM session_data sd
            INNER JOIN players p ON p.id = sd.player_id
            INNER JOIN practice_sessions ps ON ps.id = sd.session_id
            LEFT JOIN drills d ON d.id = sd.drill_id
            WHERE p.org_id = :org_id
              AND COALESCE(ps.started_at, ps.created_at)::date >= :date_start
              AND COALESCE(ps.started_at, ps.created_at)::date <= :date_end
            """
        ),
        {
            "org_id": org_id,
            "date_start": parsed.date_start,
            "date_end": parsed.date_end,
            "free_throw_pattern": FREE_THROW_CATEGORY_PATTERN,
        },
    )
    row = result.mappings().first()
    if row is None:
        return 0, 0
    return int(row["makes"]), int(row["attempts"])


async def build_org_metrics(
    db: AsyncSession,
    org_id: UUID,
    parsed: ParsedReportCriteria,
) -> ReportMetrics:
    """Aggregate org-scoped performance metrics for reports and analytics."""
    total_coaches = (
        await _count_users_for_org(db, org_id, UserRole.COACH.value)
        if _segment_includes_coaches(parsed.user_segments)
        else 0
    )
    total_players = (
        await _count_users_for_org(db, org_id, UserRole.PLAYER.value)
        if _segment_includes_players(parsed.user_segments)
        else 0
    )
    total_sessions = await _count_sessions_for_org(db, org_id, parsed)
    total_makes, total_attempts = await _aggregate_shooting_stats(db, org_id, parsed)

    return ReportMetrics(
        total_coaches=total_coaches,
        total_players=total_players,
        total_sessions=total_sessions,
        total_makes=total_makes,
        total_attempts=total_attempts,
        shooting_percent=compute_shooting_percent(total_makes, total_attempts),
    )


def _metrics_are_empty(metrics: ReportMetrics) -> bool:
    """Return True when no measurable activity exists for the criteria."""
    return (
        metrics.total_coaches == 0
        and metrics.total_players == 0
        and metrics.total_sessions == 0
        and metrics.total_attempts == 0
    )


def _criteria_to_dict(criteria: ReportCriteria) -> dict[str, Any]:
    """Serialize criteria for JSONB storage."""
    payload = criteria.model_dump(mode="json")
    return payload


def _metrics_to_dict(metrics: ReportMetrics) -> dict[str, Any]:
    """Serialize metrics for JSONB storage."""
    return metrics.model_dump(mode="json")


async def require_org_id(user: User) -> UUID:
    """Return the caller's organization id or raise 404."""
    if user.org_id is None:
        raise AppException(
            code="ORGANIZATION_NOT_FOUND",
            message="Organization profile not found",
            status_code=404,
        )
    return user.org_id


async def generate_report(
    db: AsyncSession,
    user: User,
    criteria: ReportCriteria,
) -> ReportGenerateResponse:
    """Generate and persist a report for the authenticated org admin."""
    org_id = await require_org_id(user)
    parsed = parse_report_criteria(criteria)
    metrics = await build_org_metrics(db, org_id, parsed)
    is_empty = _metrics_are_empty(metrics)
    message = EMPTY_REPORT_MESSAGE if is_empty else GENERATED_REPORT_MESSAGE

    report = OrgReport(
        org_id=org_id,
        created_by_user_id=user.id,
        criteria=_criteria_to_dict(criteria),
        metrics=_metrics_to_dict(metrics),
        status="empty" if is_empty else "completed",
        message=message,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    logger.info(
        "Generated org report %s for org %s by user %s",
        report.id,
        org_id,
        user.id,
    )

    return ReportGenerateResponse(
        message=message,
        report_id=report.id,
        data=metrics,
        criteria=criteria,
    )


async def get_report(
    db: AsyncSession,
    user: User,
    report_id: UUID,
) -> ReportDetailResponse:
    """Return a persisted report scoped to the caller's organization."""
    org_id = await require_org_id(user)
    result = await db.execute(
        select(OrgReport).where(OrgReport.id == report_id, OrgReport.org_id == org_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise AppException(
            code="REPORT_NOT_FOUND",
            message="Report not found",
            status_code=404,
        )

    criteria = ReportCriteria.model_validate(report.criteria)
    metrics = ReportMetrics.model_validate(report.metrics)
    return ReportDetailResponse(
        message=report.message,
        report_id=report.id,
        criteria=criteria,
        data=metrics,
        generated_at=report.created_at,
    )


def _build_csv_content(report: OrgReport, metrics: ReportMetrics) -> bytes:
    """Build CSV export bytes for a report."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["metric", "value"])
    writer.writerow(["report_id", str(report.id)])
    writer.writerow(["total_coaches", metrics.total_coaches])
    writer.writerow(["total_players", metrics.total_players])
    writer.writerow(["total_sessions", metrics.total_sessions])
    writer.writerow(["total_makes", metrics.total_makes])
    writer.writerow(["total_attempts", metrics.total_attempts])
    writer.writerow(["shooting_percent", metrics.shooting_percent])
    return buffer.getvalue().encode("utf-8")


def _escape_pdf_text(value: str) -> str:
    """Escape parentheses and backslashes for PDF literal strings."""
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf_content(report: OrgReport, metrics: ReportMetrics) -> bytes:
    """Build a minimal valid PDF document for the report metrics."""
    lines = [
        f"Report ID: {report.id}",
        f"Coaches: {metrics.total_coaches}",
        f"Players: {metrics.total_players}",
        f"Sessions: {metrics.total_sessions}",
        f"Makes: {metrics.total_makes}",
        f"Attempts: {metrics.total_attempts}",
        f"Shooting %: {metrics.shooting_percent}",
    ]
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


def _encode_export(content: bytes, export_format: str, report_id: UUID) -> ReportExportResponse:
    """Return a base64 export payload."""
    encoded = base64.b64encode(content).decode("ascii")
    extension = "csv" if export_format == "csv" else "pdf"
    return ReportExportResponse(
        message=EXPORT_SUCCESS_MESSAGE,
        format=export_format,  # type: ignore[arg-type]
        content_base64=encoded,
        filename=f"report-{report_id}.{extension}",
    )


async def export_report(
    db: AsyncSession,
    user: User,
    report_id: UUID,
    export_format: str,
) -> ReportExportResponse:
    """Export a stored report as CSV or PDF."""
    normalized_format = export_format.strip().lower()
    if normalized_format not in SUPPORTED_EXPORT_FORMATS:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Export format must be csv or pdf",
            status_code=400,
            details=[{"field": "format", "message": "Supported formats: csv, pdf"}],
        )

    org_id = await require_org_id(user)
    result = await db.execute(
        select(OrgReport).where(OrgReport.id == report_id, OrgReport.org_id == org_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise AppException(
            code="REPORT_NOT_FOUND",
            message="Report not found",
            status_code=404,
        )

    metrics = ReportMetrics.model_validate(report.metrics)
    try:
        if normalized_format == "csv":
            content = _build_csv_content(report, metrics)
        else:
            content = _build_pdf_content(report, metrics)
    except Exception as exc:
        logger.exception("Failed to export report %s as %s", report_id, normalized_format)
        raise AppException(
            code="EXPORT_FAILED",
            message="Unable to export the report due to a network or processing error",
            status_code=502,
        ) from exc

    logger.info("Exported org report %s as %s for org %s", report_id, normalized_format, org_id)
    return _encode_export(content, normalized_format, report_id)
