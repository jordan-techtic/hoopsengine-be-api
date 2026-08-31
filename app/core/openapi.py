from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.core.config import settings

OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Service health checks.",
    },
    {
        "name": "auth",
        "description": (
            "Coach authentication and signup flows: registration, email verification OTP, "
            "and legacy admin login/password reset."
        ),
    },
    {
        "name": "coach-auth",
        "description": (
            "Coach login, forgot-password, and verification flow (cancel/continue) endpoints "
            "for the Coach module mobile screens."
        ),
    },
    {
        "name": "reset-password",
        "description": (
            "Authenticated coach reset-password form and live password-strength validation "
            "for the Reset Password UI."
        ),
    },
    {
        "name": "support",
        "description": (
            "Support request endpoints. Submit requests with optional file attachments "
            "(POST). Super admins can list submitted requests (GET)."
        ),
    },
    {
        "name": "super-admin-subscription-plans",
        "description": (
            "Super admin subscription plan management for organization admins (`org_admin`) "
            "and coaches (`coach`). Create, update, list, and delete Stripe-backed plans. "
            "Role, currency, and billing frequency are immutable after creation."
        ),
    },
    {
        "name": "webhooks",
        "description": "Stripe webhook endpoints for subscription lifecycle sync.",
    },
    {
        "name": "super-admin-profile",
        "description": "Super admin profile management (name, email, profile image).",
    },
    {
        "name": "super-admin-organizations",
        "description": (
            "Super admin organization management. List, create, update, and remove "
            "organizations (name, contact email, phone number, address)."
        ),
    },
    {
        "name": "super-admin-users",
        "description": (
            "Super admin user management. List, create, update, and remove user accounts "
            "(coaches, players, organization admins). Super admins cannot remove their own account."
        ),
    },
    {
        "name": "super-admin-dashboard",
        "description": (
            "Super admin dashboard analytics. Organization, coach, player, session, "
            "subscription, and revenue totals for the Super Admin home screen."
        ),
    },
    {
        "name": "coach-sessions",
        "description": (
            "Coach session mode selection, recording, summary, and lifecycle actions "
            "for the Record Session and Session Summary mobile screens."
        ),
    },
    {
        "name": "coach-leaderboard",
        "description": (
            "Player leaderboard rankings, name search, and performance metric filtering "
            "for the Coach Leaderboard screen."
        ),
    },
    {
        "name": "coach-practice-plans",
        "description": (
            "Practice plan CRUD for the Coach Practice Plan screen. Authenticated coaches "
            "manage active plans and associated drills."
        ),
    },
    {
        "name": "account-settings",
        "description": (
            "Authenticated Account Settings screen APIs: change password, organization, "
            "authentication keys, push notifications, profile, and help/support."
        ),
    },
    {
        "name": "support-contact",
        "description": (
            "Public Contact Support APIs for submitting inquiries and reading support "
            "directory contact details (email, phone)."
        ),
    },
    {
        "name": "faqs",
        "description": (
            "Public FAQs for Coach and Player help screens. Use profile=player (default) "
            "for player-module articles; profile=coach for coach help articles. Includes "
            "FAQ detail and contact-support submission."
        ),
    },
    {
        "name": "coach-home",
        "description": (
            "Authenticated coach Home Screen aggregate endpoint: totals, recent activities, "
            "and attendance records for the mobile home UI."
        ),
    },
    {
        "name": "coach-sync",
        "description": (
            "Coach Offline Sync flow: Sync Now, clear local cache metadata, and read/update "
            "auto sync and sync frequency preferences."
        ),
    },
    {
        "name": "coach-sync-activity",
        "description": (
            "Coach Sync Activity screen: recent sync activity timeline and save updates."
        ),
    },
    {
        "name": "home",
        "description": (
            "Authenticated coach home split endpoints for activities, user info, and notifications."
        ),
    },
    {
        "name": "statistics",
        "description": (
            "Public player statistics for the View Statistics screen (no authentication required)."
        ),
    },
    {
        "name": "subscription-management",
        "description": (
            "Authenticated subscription management: view current plan, upgrade, and cancel."
        ),
    },
    {
        "name": "practice-plans",
        "description": (
            "Practice plan list/create/update/delete and team roster search for the "
            "Practice Plans screen."
        ),
    },
    {
        "name": "drills",
        "description": (
            "Drill catalog APIs for One Drill Step-2 and practice plan pickers: list/search, "
            "CRUD, drill detail, and continue-to-step-3 after drill selection. "
            "GET /drills/{id} is role-dispatched: verified coaches receive catalog metadata; "
            "players receive Active Drill 2 playback state (timer, status, progress)."
        ),
    },
    {
        "name": "player-drills",
        "description": (
            "Authenticated player Active Drill 1 & 2 APIs (HE-455, HE-213) under /player/drills: "
            "list assigned drills, start/stop/reset timers, drill detail, playback, and timer sync. "
            "Optional `phone` query/body field is Figma status-bar metadata (not persisted). "
            "Requires player JWT."
        ),
    },
    {
        "name": "player-active-drill",
        "description": (
            "HE-213 ticket-path aliases under /drills/{id}/play and /drills/{id}/timer for mobile "
            "clients that call /api/v1/drills/* instead of /api/v1/player/drills/*. "
            "Same request/response schemas and auth as primary player routes."
        ),
    },
    {
        "name": "player-start",
        "description": (
            "Authenticated player Start screen APIs (HE-229): GET returns quick stats and today's "
            "assigned drill list; POST starts an in-progress workout session. Drill names in POST "
            "must match assigned subteam drills from GET. Requires player JWT."
        ),
    },
    {
        "name": "coach-one-drill",
        "description": (
            "One Drill Step-1 flow: search org players, select a player, and continue to "
            "Step-2 drill selection. State is stored on the active practice_sessions row."
        ),
    },
    {
        "name": "coach-queue",
        "description": (
            "Coach sync queue for locally saved practice_sessions and session_data rows "
            "pending upload. Supports listing pending items and updating sync status."
        ),
    },
    {
        "name": "coach-drill-ideas",
        "description": (
            "Coach drill idea submission and listing for the Drill-idea submission screen."
        ),
    },
    {
        "name": "coach-edit-practice-plan",
        "description": (
            "Coach Edit Practice Plan CRUD under /coach/practice-plans."
        ),
    },
    {
        "name": "role-selection",
        "description": (
            "Public onboarding Role Selection screen APIs. List Coach/Player/Organiser options, "
            "submit a selection, and retrieve the current session without authentication."
        ),
    },
    {
        "name": "players",
        "description": (
            "Authenticated coach player management for Add Player, My Players, and Player Details "
            "screens: create, list, search, retrieve, update, and soft-delete roster players."
        ),
    },
    {
        "name": "attendance",
        "description": (
            "Authenticated coach Attendance screen APIs: search players by name or jersey number, "
            "load the present/total summary row, and start practice after marking attendance."
        ),
    },
    {
        "name": "live-practice",
        "description": (
            "Live Practice screen APIs for drill CRUD, session timer control, and per-player shot "
            "statistics. Drill list and player statistics GET endpoints are public; mutations require coach JWT."
        ),
    },
    {
        "name": "coach-remove-player",
        "description": (
            "Authenticated Remove Player confirmation modal and permanent roster removal by "
            "full_name, email, and phone credentials."
        ),
    },
    {
        "name": "player-auth",
        "description": (
            "Player module authentication and account flows: forgot-password OTP, verify-code "
            "(invitation or recovery), reset-password (JWT or recovery token), change-password, "
            "cancel-verification during signup, and player login/validate. Public except "
            "authenticated reset-password, change-password, and cancel-verification."
        ),
    },
    {
        "name": "player-profile",
        "description": (
            "Authenticated player Edit Profile screen: GET and PUT /player/profile for personal "
            "details, contact info, and avatar metadata. Requires player JWT."
        ),
    },
    {
        "name": "player-progress",
        "description": (
            "Authenticated player My Progress screen APIs: aggregate shooting stats, "
            "session history, and per-drill performance metrics. Requires player JWT."
        ),
    },
    {
        "name": "player-home",
        "description": (
            "Authenticated player Home Screen aggregate endpoint: profile header, performance "
            "totals, recent sessions, and motivational card. Requires player JWT."
        ),
    },
    {
        "name": "player-support",
        "description": (
            "Public player Contact Support APIs: submit support inquiries and retrieve "
            "support directory contact details (email, phone, operating hours)."
        ),
    },
    {
        "name": "player-drill-submissions",
        "description": (
            "Authenticated player Drill-idea submission APIs: submit, list, and retrieve "
            "custom drill ideas for tactical library review. Requires player JWT."
        ),
    },
    {
        "name": "leaderboard",
        "description": (
            "Authenticated leaderboard rankings and name search for players and coaches. "
            "Coach-only filter and POST search endpoints are also grouped here."
        ),
    },
    {
        "name": "org-admin-auth",
        "description": (
            "Public organization admin login at POST /organization/login. Returns JWT for "
            "organization dashboard APIs."
        ),
    },
    {
        "name": "org-admin-profile",
        "description": (
            "Authenticated organization admin profile management (GET/PUT /organization/profile). "
            "Supports detailed Edit Profile and management name/description/contact_info forms."
        ),
    },
    {
        "name": "org-admin-reports",
        "description": (
            "Authenticated organization admin report generation, retrieval, and CSV/PDF export."
        ),
    },
    {
        "name": "org-admin-analytics",
        "description": (
            "Authenticated organization admin analytics dashboard, filtering, and export."
        ),
    },
    {
        "name": "org-admin-billing",
        "description": (
            "Authenticated organization admin billing history and payment method updates "
            "under /admin/billing."
        ),
    },
    {
        "name": "org-admin-billing-alias",
        "description": (
            "Ticket-path billing aliases under /billing (history GET, payment-method PUT)."
        ),
    },
    {
        "name": "org-admin-custom-ui",
        "description": (
            "Authenticated custom UI design save and list under /custom-ui."
        ),
    },
    {
        "name": "org-admin-ui-design",
        "description": (
            "Ticket-path UI design aliases: save, templates, and session-limited feedback."
        ),
    },
    {
        "name": "player-role-selection",
        "description": (
            "Public player-module alias for role selection (Coach, Player, Organiser)."
        ),
    },
    {
        "name": "coach-profile",
        "description": (
            "Authenticated user profile retrieval and update for the Edit Profile screen."
        ),
    },
]


def _apply_bearer_auth(openapi_schema: dict) -> None:
    """Expose a single JWT scheme in Swagger and attach it to protected operations.

    FastAPI documents `HTTPBearer` from `Depends(HTTPBearer)`, while this app
    advertises `BearerAuth` in Authorize. Rewrite so one Authorize action works.
    """
    components = openapi_schema.setdefault("components", {})
    schemes = components.setdefault("securitySchemes", {})
    schemes["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "JWT access token from `POST /api/v1/coach/login`, `POST /api/v1/login` (player), `POST /api/v1/organization/login` (org admin), or `POST /api/v1/register`. Paste access_token only (no Bearer prefix).",
    }

    http_bearer_keys = [
        key
        for key, scheme in list(schemes.items())
        if key != "BearerAuth"
        and isinstance(scheme, dict)
        and scheme.get("type") == "http"
        and str(scheme.get("scheme", "")).lower() == "bearer"
    ]
    for key in http_bearer_keys:
        schemes.pop(key, None)

    for methods in openapi_schema.get("paths", {}).values():
        if not isinstance(methods, dict):
            continue
        for operation in methods.values():
            if not isinstance(operation, dict):
                continue
            security = operation.get("security")
            if not security:
                continue
            rewritten: list[dict] = []
            for item in security:
                if not isinstance(item, dict):
                    continue
                if any(key in item for key in http_bearer_keys):
                    rewritten.append({"BearerAuth": []})
                else:
                    rewritten.append(item)
            if rewritten:
                operation["security"] = rewritten


def setup_openapi(app: FastAPI) -> None:
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=settings.APP_NAME,
            version=settings.APP_VERSION,
            description=(
                "Hoops Engine backend API.\n\n"
                "Use **Swagger UI** at `/docs` to explore and test endpoints.\n"
                "After coach or player login (or registration), click **Authorize** and paste the JWT access token.\n\n"
                "Super Admin Manage Organizations, Manage Users, and Dashboard endpoints "
                "require a super-admin JWT (`is_super_admin=true`)."
            ),
            routes=app.routes,
            tags=OPENAPI_TAGS,
        )
        _apply_bearer_auth(openapi_schema)
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
