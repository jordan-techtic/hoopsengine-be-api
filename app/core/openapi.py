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
        "description": "Authentication endpoints for login and password reset.",
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
        "description": "JWT access token returned by `/api/v1/auth/login`.",
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
                "After logging in, click **Authorize** and paste the JWT access token.\n\n"
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
