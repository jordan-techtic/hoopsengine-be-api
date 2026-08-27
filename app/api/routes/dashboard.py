from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_super_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.dashboard import DASHBOARD_EMPTY_EXAMPLE, DASHBOARD_EXAMPLE, DashboardAnalyticsResponse
from app.schemas.errors import openapi_error
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/super-admin/dashboard", tags=["super-admin-dashboard"])

AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing, invalid, expired, or revoked JWT (`MISSING_TOKEN`, `INVALID_TOKEN`, `TOKEN_REVOKED`)",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
    403: openapi_error(
        "Authenticated user is not a super admin (`FORBIDDEN`)",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
    500: openapi_error(
        "Unexpected server error (`INTERNAL_SERVER_ERROR` or `DATABASE_ERROR`)",
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred",
    ),
}

NOT_FOUND_RESPONSE = {
    404: openapi_error(
        (
            "Unknown path under `/super-admin/dashboard` (`HTTP_404`). "
            "An empty KPI payload (all zeros) is HTTP 200, not 404."
        ),
        code="HTTP_404",
        message="Not Found",
    ),
}


@router.get(
    "",
    response_model=DashboardAnalyticsResponse,
    operation_id="getSuperAdminDashboard",
    summary="Get Super Admin dashboard analytics",
    description=(
        "Return platform KPI totals for the Super Admin dashboard after login so the UI "
        "can render Total Organizations, Total Coaches, Total Players, Total Sessions, "
        "Active Subscriptions, and Revenue Overview.\n\n"
        "This is a read-only GET. There is no request body and no query or path parameters. "
        "No rows are created, updated, or deleted.\n\n"
        "Counts:\n"
        "- `total_organizations` — all organization rows\n"
        "- `total_coaches` / `total_players` — `users.role` of `coach` / `player`, "
        "excluding soft-deleted accounts (`deleted_at` is not null). Inactive accounts "
        "are included\n"
        "- `total_sessions` — `practice_sessions` rows when that client table exists, "
        "otherwise `0`\n"
        "- `active_subscriptions` — Stripe subscription rows in `active`, `trialing`, "
        "or `past_due`. `canceled` and `unpaid` are excluded\n"
        "- `revenue_overview` — estimated monthly list-price dollars of those live "
        "subscriptions (yearly plan prices divided by 12). This is not Stripe-collected "
        "cash revenue\n\n"
        "`description`, `link`, and `error` are always `null` on success so the Super "
        "Admin UI can bind optional subtitle, navigation, and inline-error slots. "
        "Core-module navigation (organizations, coaches, players, subscriptions) is "
        "client-side.\n\n"
        "An all-zero payload is a successful empty state (`200`), not a missing "
        "resource. The dashboard can load immediately after login even when the "
        "platform has no subscriptions or sessions yet. `400`, `409`, and `422` are not "
        "returned (no body or query to validate).\n\n"
        "**Requires super admin JWT** (`Authorization: Bearer <access_token>` from "
        "`POST /api/v1/auth/login`)."
    ),
    responses={
        200: {
            "description": (
                "KPI totals. Zeros are a valid empty state after login "
                "(not `404`)."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "populated": {
                            "summary": "Platform with data",
                            "value": DASHBOARD_EXAMPLE,
                        },
                        "empty": {
                            "summary": "Empty state (zeros)",
                            "value": DASHBOARD_EMPTY_EXAMPLE,
                        },
                    }
                }
            },
        },
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSE,
    },
)
async def get_super_admin_dashboard(
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> DashboardAnalyticsResponse:
    """Return Super Admin dashboard KPIs. Requires a super-admin JWT."""
    return await dashboard_service.get_dashboard_analytics(db)
