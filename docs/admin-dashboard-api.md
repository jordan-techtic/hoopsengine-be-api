# Super Admin Dashboard API

This API returns platform KPI totals for the Super Admin dashboard (organizations, coaches, players, sessions, active subscriptions, and revenue overview).

Base path:

```text
/api/v1/super-admin/dashboard
```

All endpoints require a bearer token for a `super_admin` user.

---

## Swagger UI (testing)

1. Open `http://<host>:<port>/docs`
2. Click **Authorize** and paste the JWT from `POST /api/v1/auth/login`
3. Open the **super-admin-dashboard** tag
4. Use **Try it out** for:
   - `GET /super-admin/dashboard`

---

## GET `/super-admin/dashboard`

Return analytics for the Super Admin dashboard so the UI can render metric cards after login.

### Headers

```http
Authorization: Bearer <access_token>
Accept: application/json
```

### Example response — `200 OK`

```json
{
  "total_organizations": 100,
  "total_coaches": 50,
  "total_players": 200,
  "total_sessions": 150,
  "active_subscriptions": 75,
  "revenue_overview": 5000,
  "description": null,
  "link": null,
  "error": null
}
```

| Field | Meaning |
|---|---|
| `total_organizations` | All rows in `organizations` |
| `total_coaches` | Non-deleted `users` with `role=coach` (includes inactive accounts) |
| `total_players` | Non-deleted `users` with `role=player` |
| `total_sessions` | Rows in `practice_sessions`, or `0` if that table is not in this database |
| `active_subscriptions` | Stripe subscriptions with status `active`, `trialing`, or `past_due` |
| `revenue_overview` | Estimated monthly list-price revenue in whole dollars (yearly prices ÷ 12) |
| `description` | Always `null` (optional UI subtitle slot) |
| `link` | Always `null` (module navigation is client-side) |
| `error` | Always `null` on success |

When the platform has no subscriptions or sessions yet, those fields are `0`. That is a successful empty state, not an error — the dashboard still returns `200` so it can load after login.

### Error responses

`401 Unauthorized` — missing or invalid JWT (`MISSING_TOKEN`, `INVALID_TOKEN`, `TOKEN_REVOKED`)

`403 Forbidden` — user is not a super admin (`FORBIDDEN`)
