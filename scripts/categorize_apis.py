"""Categorize all 207 APIs by role and output flow-wise testing checklist."""
import re
from app.main import app

# Role assignment rules (first match wins)
ROLE_RULES = [
    ("Super Admin", lambda p, t: p.startswith("/api/v1/super-admin") or t.startswith("super-admin")),
    ("Stripe / System", lambda p, t: p.startswith("/api/v1/webhooks") or p == "/api/v1/health" or p == "/"),
    ("Organization Admin", lambda p, t: (
        p.startswith("/api/v1/organization")
        or p.startswith("/api/v1/admin/")
        or p.startswith("/api/v1/analytics")
        or p.startswith("/api/v1/reports")
        or p.startswith("/api/v1/custom-ui")
        or p.startswith("/api/v1/ui-design")
        or t.startswith("org-admin")
    )),
    ("Coach", lambda p, t: (
        p.startswith("/api/v1/coach/")
        or p.startswith("/api/v1/register")
        or p.startswith("/api/v1/resend-verification")
        or p.startswith("/api/v1/verify-email")
        or (p.startswith("/api/v1/auth/") and "coach" not in p)
        or p.startswith("/api/v1/reset-password")
        or p.startswith("/api/v1/role-selection")
        or p.startswith("/api/v1/profile") and not p.startswith("/api/v1/super-admin")
        or p.startswith("/api/v1/home/")
        or p.startswith("/api/v1/sessions")
        or p.startswith("/api/v1/live_practice")
        or p.startswith("/api/v1/drill-ideas")
        or p.startswith("/api/v1/attendance")
        or (p.startswith("/api/v1/drills") and not p.startswith("/api/v1/player"))
        or (p.startswith("/api/v1/practice-plans") and not p.startswith("/api/v1/admin"))
        or (p.startswith("/api/v1/players") and not p.startswith("/api/v1/admin"))
        or (p.startswith("/api/v1/teams") and not p.startswith("/api/v1/admin"))
        or t in ("coach-auth", "coach-home", "coach-one-drill", "coach-edit-practice-plan",
                 "coach-queue", "coach-remove-player", "coach-sync", "coach-sync-activity",
                 "coach-sessions", "coach-profile", "coach-drill-ideas", "live-practice",
                 "attendance", "drills", "practice-plans", "players", "teams", "home",
                 "role-selection", "reset-password", "auth")
    )),
    ("Player", lambda p, t: (
        p.startswith("/api/v1/player/")
        or p.startswith("/api/v1/login")
        or t.startswith("player")
    )),
    ("Shared / Multi-Role", lambda p, t: (
        p.startswith("/api/v1/subscription")
        or p.startswith("/api/v1/leaderboard")
        or p.startswith("/api/v1/statistics")
        or p.startswith("/api/v1/faqs")
        or p.startswith("/api/v1/support")
        or p.startswith("/api/v1/account/settings")
        or p.startswith("/api/v1/billing")
        or t in ("subscription-management", "leaderboard", "statistics", "faqs",
                 "support", "support-contact", "account-settings", "org-admin-billing-alias")
    )),
]

# Flow order within each role (module prefix -> sort key)
FLOW_ORDER = {
    "Super Admin": [
        ("01-auth", ["/api/v1/auth/login", "/api/v1/auth/forgot-password", "/api/v1/auth/validate-reset-token", "/api/v1/auth/reset-password", "/api/v1/auth/logout"]),
        ("02-dashboard", ["/api/v1/super-admin/dashboard"]),
        ("03-organizations", ["/api/v1/super-admin/organizations"]),
        ("04-users", ["/api/v1/super-admin/users"]),
        ("05-subscription-plans-stripe", ["/api/v1/super-admin/subscription-plans"]),
        ("06-profile", ["/api/v1/super-admin/profile"]),
        ("07-support", ["/api/v1/support-requests"]),
    ],
    "Organization Admin": [
        ("01-auth", ["/api/v1/organization/login", "/api/v1/admin/reset-password", "/api/v1/admin/change-password", "/api/v1/organization/change-password"]),
        ("02-profile", ["/api/v1/organization/profile"]),
        ("03-teams", ["/api/v1/admin/teams", "/api/v1/teams"]),
        ("04-coaches", ["/api/v1/admin/invite-coach", "/api/v1/admin/search-coaches", "/api/v1/admin/coaches"]),
        ("05-players", ["/api/v1/admin/players", "/api/v1/players"]),
        ("06-practice-plans", ["/api/v1/admin/practice-plans", "/api/v1/practice-plans"]),
        ("07-analytics-reports", ["/api/v1/analytics", "/api/v1/reports"]),
        ("08-subscription-billing-stripe", ["/api/v1/admin/subscription", "/api/v1/admin/billing", "/api/v1/billing"]),
        ("09-custom-ui", ["/api/v1/custom-ui", "/api/v1/ui-design"]),
        ("10-settings-help", ["/api/v1/account/settings", "/api/v1/faqs", "/api/v1/support"]),
    ],
    "Coach": [
        ("01-auth-registration", ["/api/v1/register", "/api/v1/verify-email", "/api/v1/resend-verification", "/api/v1/coach/login", "/api/v1/coach/forgot-password", "/api/v1/coach/cancel-verification", "/api/v1/coach/continue-verification", "/api/v1/auth/"]),
        ("02-role-selection", ["/api/v1/role-selection"]),
        ("03-home-dashboard", ["/api/v1/coach/home", "/api/v1/home/"]),
        ("04-profile-settings", ["/api/v1/profile", "/api/v1/reset-password", "/api/v1/account/settings"]),
        ("05-one-drill-flow", ["/api/v1/coach/drills/search", "/api/v1/coach/drills/select_player", "/api/v1/coach/drills/continue", "/api/v1/drills", "/api/v1/sessions"]),
        ("06-attendance-daily-options", ["/api/v1/attendance"]),
        ("07-live-practice", ["/api/v1/live_practice"]),
        ("08-practice-plans", ["/api/v1/practice-plans", "/api/v1/coach/practice-plans"]),
        ("09-players-teams", ["/api/v1/players", "/api/v1/teams", "/api/v1/coach/remove_player", "/api/v1/coach/confirm_removal"]),
        ("10-leaderboard-statistics", ["/api/v1/leaderboard", "/api/v1/statistics"]),
        ("11-subscription-stripe", ["/api/v1/subscription"]),
        ("12-offline-sync", ["/api/v1/coach/sync", "/api/v1/coach/sync-activity", "/api/v1/coach/queue", "/api/v1/coach/clear-cache"]),
        ("13-help-support", ["/api/v1/drill-ideas", "/api/v1/faqs", "/api/v1/support"]),
    ],
    "Player": [
        ("01-auth-invitation", ["/api/v1/player/verify-code", "/api/v1/player/cancel-verification", "/api/v1/login", "/api/v1/player/forgot-password", "/api/v1/player/reset-password-with-token", "/api/v1/player/reset-password", "/api/v1/player/change-password"]),
        ("02-role-selection", ["/api/v1/player/role-selection"]),
        ("03-home", ["/api/v1/player/home"]),
        ("04-profile", ["/api/v1/player/profile"]),
        ("05-workout-drills", ["/api/v1/player/start", "/api/v1/player/drills"]),
        ("06-progress", ["/api/v1/player/my-progress", "/api/v1/player/session-history", "/api/v1/player/drill-performance"]),
        ("07-leaderboard", ["/api/v1/leaderboard"]),
        ("08-help-support", ["/api/v1/player/drill-submissions", "/api/v1/faqs", "/api/v1/support"]),
    ],
}


def classify(path, tag):
    for role, fn in ROLE_RULES:
        if fn(path, tag):
            return role
    return "Uncategorized"


def flow_sort_key(role, path):
    if role not in FLOW_ORDER:
        return (99, path)
    for i, (_, prefixes) in enumerate(FLOW_ORDER[role]):
        for prefix in prefixes:
            if path.startswith(prefix) or path == prefix:
                return (i, path)
    return (98, path)


paths = app.openapi()["paths"]
entries = []
for path, methods in sorted(paths.items()):
    for method in sorted(methods.keys()):
        if method not in ("get", "post", "put", "patch", "delete"):
            continue
        op = methods[method]
        tag = op.get("tags", [""])[0]
        summary = op.get("summary", "")
        role = classify(path, tag)
        entries.append({
            "method": method.upper(),
            "path": path,
            "tag": tag,
            "summary": summary,
            "role": role,
        })

ROLE_SEQUENCE = ["Stripe / System", "Super Admin", "Organization Admin", "Coach", "Player", "Shared / Multi-Role", "Uncategorized"]

for role in ROLE_SEQUENCE:
    group = [e for e in entries if e["role"] == role]
    group.sort(key=lambda e: flow_sort_key(role, e["path"]))
    print(f"\n{'='*80}")
    print(f"  {role.upper()} — {len(group)} APIs")
    print(f"{'='*80}")
    for idx, e in enumerate(group, 1):
        print(f"{idx:3}. [{e['method']:6}] {e['path']}")
        print(f"     Tag: {e['tag']} | {e['summary']}")

print(f"\n\nGRAND TOTAL: {len(entries)} API operations")
