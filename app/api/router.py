from fastapi import APIRouter

from app.api.routes import (
    auth,
    health,
    organizations,
    profile,
    subscription_plans,
    support,
    users,
    webhooks,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(support.router)
api_router.include_router(subscription_plans.router)
api_router.include_router(webhooks.router)
api_router.include_router(profile.router)
api_router.include_router(organizations.router)
api_router.include_router(users.router)
