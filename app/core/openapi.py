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
        "name": "admin-subscription-plans",
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
        "name": "admin-profile",
        "description": "Super admin profile management (name, email, profile image).",
    },
]


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
                "After logging in, click **Authorize** and paste the JWT access token."
            ),
            routes=app.routes,
            tags=OPENAPI_TAGS,
        )
        openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})
        openapi_schema["components"]["securitySchemes"]["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT access token returned by `/api/v1/auth/login`.",
        }
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
