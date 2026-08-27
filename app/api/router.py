from fastapi import APIRouter

from app.api.routes import (
    account_settings,
    auth,
    coach,
    coach_practice_plans,
    coach_profile,
    dashboard,
    drills,
    faqs,
    health,
    leaderboard,
    organizations,
    practice_plans,
    profile,
    register,
    reset_password,
    sessions,
    subscription_plans,
    subscription_management,
    support,
    support_contact,
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
api_router.include_router(support_contact.router)
api_router.include_router(faqs.router)
api_router.include_router(subscription_plans.router)
api_router.include_router(subscription_management.router)
api_router.include_router(webhooks.router)
api_router.include_router(profile.router)
api_router.include_router(coach_profile.router)
api_router.include_router(coach_practice_plans.router)
api_router.include_router(account_settings.router)
api_router.include_router(organizations.router)
api_router.include_router(users.router)
api_router.include_router(dashboard.router)
api_router.include_router(sessions.router)
api_router.include_router(leaderboard.router)
api_router.include_router(practice_plans.router)
api_router.include_router(drills.router)
