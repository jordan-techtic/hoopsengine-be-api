from fastapi import APIRouter

from app.api.routes import (
    auth,
    coach,
    coach_profile,
    dashboard,
    health,
    leaderboard,
    organizations,
    practice_plans,
    profile,
    register,
    reset_password,
    sessions,
    subscription_plans,
    support,
    users,
    verification,
    webhooks,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(register.router)
api_router.include_router(verification.router)
api_router.include_router(coach.router)
api_router.include_router(reset_password.router)
api_router.include_router(auth.router)
api_router.include_router(support.router)
api_router.include_router(subscription_plans.router)
api_router.include_router(webhooks.router)
api_router.include_router(profile.router)
api_router.include_router(coach_profile.router)
api_router.include_router(organizations.router)
api_router.include_router(users.router)
api_router.include_router(dashboard.router)
api_router.include_router(sessions.router)
api_router.include_router(leaderboard.router)
api_router.include_router(practice_plans.router)
