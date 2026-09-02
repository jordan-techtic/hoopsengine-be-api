"""Generate master 1-207 API testing checklist in role flow order."""
from app.main import app

# Master flow: (section, role, items as path prefixes or exact paths)
MASTER_FLOW = [
    ("A. Infrastructure", "System", ["GET /", "GET /api/v1/health"]),
    ("B. Super Admin — Auth", "Super Admin", [
        "POST /api/v1/auth/login",
        "POST /api/v1/auth/forgot-password",
        "POST /api/v1/auth/validate-reset-token",
        "POST /api/v1/auth/reset-password",
    ]),
    ("C. Super Admin — Dashboard", "Super Admin", ["GET /api/v1/super-admin/dashboard"]),
    ("D. Super Admin — Organizations", "Super Admin", [
        "GET /api/v1/super-admin/organizations",
        "POST /api/v1/super-admin/organizations",
        "PUT /api/v1/super-admin/organizations/{organization_id}",
        "DELETE /api/v1/super-admin/organizations/{organization_id}",
    ]),
    ("E. Super Admin — Users", "Super Admin", [
        "GET /api/v1/super-admin/users",
        "POST /api/v1/super-admin/users",
        "PUT /api/v1/super-admin/users/{user_id}",
        "DELETE /api/v1/super-admin/users/{user_id}",
    ]),
    ("F. Super Admin — Stripe Subscription Plans", "Super Admin", [
        "GET /api/v1/super-admin/subscription-plans/currencies",
        "GET /api/v1/super-admin/subscription-plans",
        "POST /api/v1/super-admin/subscription-plans",
        "GET /api/v1/super-admin/subscription-plans/{plan_id}",
        "PUT /api/v1/super-admin/subscription-plans/{plan_id}",
        "DELETE /api/v1/super-admin/subscription-plans/{plan_id}",
    ]),
    ("G. Super Admin — Profile", "Super Admin", [
        "GET /api/v1/super-admin/profile",
        "PUT /api/v1/super-admin/profile",
        "GET /api/v1/super-admin/profile/avatar",
    ]),
    ("H. Super Admin — Support Requests", "Super Admin", [
        "GET /api/v1/support-requests",
        "POST /api/v1/support-requests",
        "GET /api/v1/support-requests/{request_id}/attachment",
    ]),
    ("I. Super Admin — Logout", "Super Admin", ["POST /api/v1/auth/logout"]),
    ("J. Organization Admin — Auth", "Org Admin", [
        "POST /api/v1/organization/login",
        "POST /api/v1/admin/reset-password",
        "GET /api/v1/admin/reset-password/validate",
        "POST /api/v1/admin/change-password",
        "POST /api/v1/organization/change-password",
    ]),
    ("K. Organization Admin — Profile", "Org Admin", [
        "GET /api/v1/organization/profile",
        "PUT /api/v1/organization/profile",
    ]),
    ("L. Organization Admin — Teams", "Org Admin", [
        "POST /api/v1/admin/teams",
        "GET /api/v1/admin/teams/{team_id}",
        "PUT /api/v1/admin/teams/{team_id}",
        "DELETE /api/v1/admin/teams/{team_id}",
        "GET /api/v1/teams",
        "POST /api/v1/teams",
        "GET /api/v1/teams/search",
        "GET /api/v1/teams/{team_id}",
        "PUT /api/v1/teams/{team_id}",
        "DELETE /api/v1/teams/{team_id}",
    ]),
    ("M. Organization Admin — Coaches", "Org Admin", [
        "POST /api/v1/admin/invite-coach",
        "GET /api/v1/admin/search-coaches",
        "GET /api/v1/admin/coaches/{coach_id}",
        "PUT /api/v1/admin/coaches/{coach_id}",
        "DELETE /api/v1/admin/coaches/{coach_id}",
    ]),
    ("N. Organization Admin — Players", "Org Admin", [
        "GET /api/v1/admin/players/{player_id}",
        "PUT /api/v1/admin/players/{player_id}",
        "GET /api/v1/admin/players/{player_id}/removal",
        "DELETE /api/v1/admin/players/{player_id}",
    ]),
    ("O. Organization Admin — Practice Plans", "Org Admin", [
        "GET /api/v1/admin/practice-plans",
        "POST /api/v1/admin/practice-plans",
        "PUT /api/v1/admin/practice-plans/{plan_id}",
        "DELETE /api/v1/admin/practice-plans/{plan_id}",
        "GET /api/v1/practice-plans",
        "POST /api/v1/practice-plans",
        "POST /api/v1/practice-plans/assign",
        "GET /api/v1/practice-plans/search",
        "PUT /api/v1/practice-plans/{plan_id}",
        "DELETE /api/v1/practice-plans/{plan_id}",
    ]),
    ("P. Organization Admin — Analytics & Reports", "Org Admin", [
        "GET /api/v1/analytics",
        "POST /api/v1/analytics/filter",
        "POST /api/v1/analytics/export",
        "POST /api/v1/reports/generate",
        "GET /api/v1/reports/{report_id}",
        "POST /api/v1/reports/export",
    ]),
    ("Q. Organization Admin — Stripe Billing & Subscription", "Org Admin", [
        "GET /api/v1/admin/subscription",
        "POST /api/v1/admin/subscription/upgrade",
        "GET /api/v1/admin/billing/history",
        "POST /api/v1/admin/billing/payment-method",
        "GET /api/v1/billing/history",
        "PUT /api/v1/billing/payment-method",
        "GET /api/v1/subscription",
        "POST /api/v1/subscription/upgrade",
        "POST /api/v1/subscription/cancel",
    ]),
    ("R. Organization Admin — Custom UI", "Org Admin", [
        "GET /api/v1/custom-ui/designs",
        "POST /api/v1/custom-ui/design",
        "GET /api/v1/ui-design/templates",
        "POST /api/v1/ui-design/save",
        "POST /api/v1/ui-design/feedback",
    ]),
    ("S. Organization Admin — Settings & Help", "Org Admin", [
        "PUT /api/v1/account/settings/profile",
        "PUT /api/v1/account/settings/organization",
        "POST /api/v1/account/settings/change-password",
        "PATCH /api/v1/account/settings/push-notifications",
        "PUT /api/v1/account/settings/authentication-keys",
        "GET /api/v1/account/settings/help-support",
        "POST /api/v1/account/settings/help-support/contact",
        "GET /api/v1/faqs",
        "GET /api/v1/faqs/{faq_id}",
        "POST /api/v1/faqs/contact-support",
        "GET /api/v1/support/contact/info",
        "POST /api/v1/support/contact",
        "GET /api/v1/leaderboard",
        "GET /api/v1/leaderboard/filter",
        "GET /api/v1/leaderboard/search",
        "POST /api/v1/leaderboard/search",
    ]),
    ("T. Coach — Registration & Auth", "Coach", [
        "POST /api/v1/register",
        "POST /api/v1/verify-email",
        "POST /api/v1/resend-verification-code",
        "GET /api/v1/coach/continue-verification",
        "POST /api/v1/coach/cancel-verification",
        "POST /api/v1/coach/login",
        "POST /api/v1/coach/forgot-password",
        "POST /api/v1/reset-password",
        "GET /api/v1/reset-password/validate",
    ]),
    ("U. Coach — Role Selection", "Coach", [
        "GET /api/v1/role-selection/roles",
        "GET /api/v1/role-selection",
        "POST /api/v1/role-selection",
    ]),
    ("V. Coach — Home Dashboard", "Coach", [
        "GET /api/v1/coach/home",
        "GET /api/v1/home/user-info",
        "GET /api/v1/home/activities",
        "GET /api/v1/home/notifications",
    ]),
    ("W. Coach — Profile", "Coach", [
        "GET /api/v1/profile",
        "PUT /api/v1/profile",
    ]),
    ("X. Coach — One Drill Flow (Step 1→3)", "Coach", [
        "POST /api/v1/coach/drills/search",
        "POST /api/v1/coach/drills/select_player",
        "POST /api/v1/coach/drills/continue",
        "GET /api/v1/drills",
        "GET /api/v1/drills/search",
        "GET /api/v1/drills/{drill_id}",
        "POST /api/v1/drills/continue",
        "GET /api/v1/sessions/modes",
        "GET /api/v1/sessions/modes/{mode}",
        "POST /api/v1/sessions",
        "POST /api/v1/sessions/record",
        "PUT /api/v1/sessions/record/{session_id}",
        "GET /api/v1/sessions/summary",
        "GET /api/v1/sessions/{session_id}",
        "PUT /api/v1/sessions/{session_id}",
        "POST /api/v1/sessions/{session_id}/next-drill",
        "POST /api/v1/sessions/{session_id}/end-practice",
    ]),
    ("Y. Coach — Attendance (Daily Options)", "Coach", [
        "GET /api/v1/attendance/players/search",
        "GET /api/v1/attendance/summary",
        "POST /api/v1/attendance/start-practice",
    ]),
    ("Z. Coach — Live Practice", "Coach", [
        "GET /api/v1/live_practice/drills",
        "POST /api/v1/live_practice/drills",
        "PUT /api/v1/live_practice/drills/{drill_id}",
        "DELETE /api/v1/live_practice/drills/{drill_id}",
        "POST /api/v1/live_practice/timer/start",
        "GET /api/v1/live_practice/timer/status",
        "POST /api/v1/live_practice/timer/stop",
        "POST /api/v1/live_practice/players/{player_id}/shots",
        "GET /api/v1/live_practice/players/{player_id}/statistics",
    ]),
    ("AA. Coach — Practice Plans", "Coach", [
        "GET /api/v1/coach/practice-plans/{plan_id}",
        "POST /api/v1/coach/practice-plans",
        "PUT /api/v1/coach/practice-plans/{plan_id}",
        "DELETE /api/v1/coach/practice-plans/{plan_id}",
    ]),
    ("AB. Coach — Player Management", "Coach", [
        "GET /api/v1/players",
        "GET /api/v1/players/search",
        "POST /api/v1/players",
        "GET /api/v1/players/{player_id}",
        "PUT /api/v1/players/{player_id}",
        "GET /api/v1/coach/confirm_removal",
        "POST /api/v1/coach/remove_player",
        "DELETE /api/v1/players/{player_id}",
    ]),
    ("AC. Coach — Drill Catalog", "Coach", [
        "POST /api/v1/drills",
        "PUT /api/v1/drills/{drill_id}",
        "DELETE /api/v1/drills/{drill_id}",
    ]),
    ("AD. Coach — Leaderboard & Statistics", "Coach", [
        "GET /api/v1/statistics/{player_id}",
    ]),
    ("AE. Coach — Stripe Subscription", "Coach", []),  # already in org admin shared - skip dup
    ("AF. Coach — Offline Sync", "Coach", [
        "GET /api/v1/coach/sync/preferences",
        "PUT /api/v1/coach/sync/preferences",
        "POST /api/v1/coach/sync",
        "GET /api/v1/coach/sync-activity",
        "POST /api/v1/coach/sync-activity/save",
        "GET /api/v1/coach/queue",
        "POST /api/v1/coach/queue",
        "POST /api/v1/coach/clear-cache",
    ]),
    ("AG. Coach — Help & Drill Ideas", "Coach", [
        "POST /api/v1/drill-ideas",
        "GET /api/v1/drill-ideas",
    ]),
    ("AH. Player — Invitation & Auth", "Player", [
        "POST /api/v1/player/verify-code",
        "GET /api/v1/player/cancel-verification",
        "POST /api/v1/player/cancel-verification",
        "GET /api/v1/login/validate",
        "POST /api/v1/login",
        "POST /api/v1/player/forgot-password",
        "POST /api/v1/player/reset-password-with-token",
        "POST /api/v1/player/reset-password",
        "POST /api/v1/player/change-password",
    ]),
    ("AI. Player — Role Selection", "Player", [
        "GET /api/v1/player/role-selection",
        "POST /api/v1/player/role-selection",
    ]),
    ("AJ. Player — Home & Profile", "Player", [
        "GET /api/v1/player/home",
        "GET /api/v1/player/profile",
        "PUT /api/v1/player/profile",
    ]),
    ("AK. Player — Workout / Training", "Player", [
        "GET /api/v1/player/start",
        "POST /api/v1/player/start",
        "GET /api/v1/player/drills",
        "GET /api/v1/player/drills/{drill_id}",
        "POST /api/v1/player/drills/start",
        "POST /api/v1/player/drills/{drill_id}/play",
        "PUT /api/v1/player/drills/{drill_id}/timer",
        "POST /api/v1/player/drills/{drill_id}/stop",
        "POST /api/v1/player/drills/reset",
        "POST /api/v1/drills/{drill_id}/play",
        "PUT /api/v1/drills/{drill_id}/timer",
    ]),
    ("AL. Player — Progress", "Player", [
        "GET /api/v1/player/my-progress",
        "GET /api/v1/player/session-history",
        "GET /api/v1/player/drill-performance",
    ]),
    ("AM. Player — Help & Support", "Player", [
        "POST /api/v1/player/drill-submissions",
        "GET /api/v1/player/drill-submissions",
        "GET /api/v1/player/drill-submissions/{submission_id}",
        "GET /api/v1/support/contact",
        "POST /api/v1/support/inquiries",
    ]),
    ("AN. Stripe Webhook", "System", ["POST /api/v1/webhooks/stripe"]),
]

paths = app.openapi()["paths"]
all_ops = []
for path, methods in paths.items():
    for method, op in methods.items():
        if method not in ("get", "post", "put", "patch", "delete"):
            continue
        key = f"{method.upper()} {path}"
        all_ops.append((key, method.upper(), path, op.get("summary", ""), op.get("tags", [""])[0]))

op_map = {k: v for k, *v in [(f"{m} {p}", m, p, s, t) for k, m, p, s, t in all_ops]}

ordered = []
seen = set()
for section, role, keys in MASTER_FLOW:
    for key in keys:
        if key in op_map and key not in seen:
            m, p, s, t = op_map[key]
            ordered.append((section, role, m, p, s, t))
            seen.add(key)

# append any missing
missing = []
for key, m, p, s, t in all_ops:
    if key not in seen:
        missing.append((m, p, s, t))
        ordered.append(("Unassigned", "?", m, p, s, t))

print(f"Ordered: {len(ordered)} | Missing from flow: {len(missing)}")
if missing:
    for m, p, s, t in missing:
        print(f"  MISSING: {m} {p}")

print("\n# | Seq | Role | Section | Method | Endpoint | Description")
print("---")
for i, (section, role, m, p, s, t) in enumerate(ordered, 1):
    auth = "Bearer JWT" if p not in ("/", "/api/v1/health", "/api/v1/webhooks/stripe") and not any(
        x in p for x in ("login", "register", "verify", "forgot", "reset-password", "validate", "health", "webhooks/stripe", "faqs", "support/contact/info")
    ) else "Public/Special"
    print(f"| {i} | {role} | {section} | `{m}` | `{p}` | {s} |")
