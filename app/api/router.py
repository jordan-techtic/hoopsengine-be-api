from fastapi import APIRouter

from app.api.routes import (
    account_settings,
    attendance,
    auth,
    coach,
    coach_practice_plans,
    coach_profile,
    coach_remove_player,
    dashboard,
    drills,
    faqs,
    health,
    leaderboard,
    live_practice,
    organizations,
    players,
    practice_plans,
    profile,
    register,
    reset_password,
    role_selection,
    sessions,
    subscription_management,
    subscription_plans,
    support,
    support_contact,
    users,
    verification,
    webhooks,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(register.router)
api_router.include_router(role_selection.router)
api_router.include_router(verification.router)
api_router.include_router(coach.router)
api_router.include_router(coach_remove_player.router)
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
api_router.include_router(attendance.router)
api_router.include_router(organizations.router)
api_router.include_router(players.router)
api_router.include_router(users.router)
api_router.include_router(dashboard.router)
api_router.include_router(sessions.router)
api_router.include_router(leaderboard.router)
api_router.include_router(live_practice.router)
api_router.include_router(practice_plans.router)
api_router.include_router(drills.router)
