# Super Admin Stripe Subscription API

This document describes the super-admin APIs for managing Stripe-backed subscription plans in the Hoops Engine admin panel.

Base path:

```text
/api/v1/super-admin/subscription-plans
```

Webhook path:

```text
/api/v1/webhooks/stripe
```

All super-admin endpoints require a **super admin JWT**. Authorize in Swagger UI via **Authorize**.

Subscription plans are separated by **role**:

| Role | Value | Admin UI section |
|---|---|---|
| Organization Admin | `org_admin` | Organization subscription plans |
| Coach | `coach` | Coach subscription plans |

Every list, get, update, and delete call must include the correct `role` so organization and coach plans stay isolated.

---

## Environment variables

Add these to `.env` on the server:

```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_MIGRATION_PRORATION_BEHAVIOR=none
```

| Variable | Description |
|---|---|
| `STRIPE_SECRET_KEY` | Stripe secret key used by the backend |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key for frontend checkout (if needed later) |
| `STRIPE_WEBHOOK_SECRET` | Signing secret from the Stripe webhook endpoint |
| `STRIPE_PRICE_MIGRATION_PRORATION_BEHAVIOR` | Stripe proration behavior when migrating subscribers to a new price (`none`, `create_prorations`, etc.) |

Email notifications on price change use the existing SendGrid settings:

```env
SENDGRID_API_KEY=...
SENDGRID_FROM_EMAIL=...
SENDGRID_FROM_NAME=...
```

---

## Python dependency

Install the Stripe SDK:

```bash
pip install -r requirements.txt
```

This includes:

```text
stripe>=11.0.0
```

---

## Frontend integration flow

### 1. Load currencies for dropdown

**GET** `/super-admin/subscription-plans/currencies`

Use this to populate the currency dropdown when creating a plan.

```json
{
  "items": [
    { "code": "USD", "name": "USD" },
    { "code": "EUR", "name": "EUR" }
  ]
}
```

### 2. Create plan form fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `role` | `"org_admin"` \| `"coach"` | Yes | Immutable after create. Controls which limit fields are shown |
| `name` | string | Yes | Plan name |
| `billing_frequency` | `"monthly"` \| `"yearly"` | Yes | Immutable after create |
| `currency` | string (3-letter ISO) | Yes | Immutable after create |
| `price_amount` | decimal string/number | Yes | Example: `49.00` |
| `teams_limit_type` | `"limited"` \| `"unlimited"` | Yes | |
| `teams_count` | integer | Conditional | Required when teams are limited |
| `coaches_limit_type` | `"limited"` \| `"unlimited"` | Org only | Omit for coach plans |
| `coaches_count` | integer | Org + limited coaches | |
| `players_limit_type` | `"limited"` \| `"unlimited"` | Yes | |
| `players_count` | integer | Conditional | Required when players are limited |
| `historical_records_duration` | enum | Yes | See values below |
| `is_active` | boolean | No | Default `true` |
| `include_offline_sync` | boolean | No | Default `false`. Adds "Offline Recording & Auto Sync" as a plan feature |
| `description` | string | No | |
| `features` | string[] | No | Dynamic feature list |

#### `historical_records_duration` values

- `1_month`
- `3_months`
- `6_months`
- `1_year`
- `unlimited`

### 3. Organization admin plan examples

#### Starter (monthly)

```json
{
  "role": "org_admin",
  "name": "Starter Plan",
  "billing_frequency": "monthly",
  "currency": "USD",
  "price_amount": "49.00",
  "teams_limit_type": "limited",
  "teams_count": 3,
  "coaches_limit_type": "limited",
  "coaches_count": 3,
  "players_limit_type": "limited",
  "players_count": 45,
  "historical_records_duration": "3_months",
  "is_active": true,
  "include_offline_sync": false,
  "description": "Suitable for small basketball academies.",
  "features": [
    "Manage up to 3 Teams",
    "Add up to 3 Coaches",
    "Add up to 45 Players",
    "Online Practice Session Recording",
    "Basic Player & Team Statistics",
    "Team Leaderboard",
    "Historical Records (Last 3 Months)",
    "Standard Support"
  ]
}
```

#### Professional (yearly)

```json
{
  "role": "org_admin",
  "name": "Professional Plan",
  "billing_frequency": "yearly",
  "currency": "USD",
  "price_amount": "499.00",
  "teams_limit_type": "limited",
  "teams_count": 15,
  "coaches_limit_type": "limited",
  "coaches_count": 20,
  "players_limit_type": "limited",
  "players_count": 300,
  "historical_records_duration": "1_year",
  "is_active": true,
  "include_offline_sync": true,
  "description": "Suitable for growing basketball organizations.",
  "features": [
    "Manage up to 15 Teams",
    "Add up to 20 Coaches",
    "Add up to 300 Players",
    "Offline Recording & Auto Sync",
    "Advanced Player & Team Statistics",
    "Organization Analytics Dashboard",
    "Organization Leaderboard",
    "PDF & Excel Report Export",
    "Historical Records (Last 1 Year)",
    "Priority Support"
  ]
}
```

#### Ultimate (yearly only)

```json
{
  "role": "org_admin",
  "name": "Ultimate Plan",
  "billing_frequency": "yearly",
  "currency": "USD",
  "price_amount": "999.00",
  "teams_limit_type": "unlimited",
  "teams_count": null,
  "coaches_limit_type": "unlimited",
  "coaches_count": null,
  "players_limit_type": "unlimited",
  "players_count": null,
  "historical_records_duration": "unlimited",
  "is_active": true,
  "include_offline_sync": true,
  "description": "Suitable for large basketball organizations.",
  "features": [
    "Unlimited Teams",
    "Unlimited Coaches",
    "Unlimited Players",
    "Unlimited Historical Records",
    "Cross-Season Performance Analytics",
    "API Access",
    "Custom Reports",
    "Dedicated Support"
  ]
}
```

### 4. Coach plan examples

#### Coach Starter

```json
{
  "role": "coach",
  "name": "Starter Plan",
  "billing_frequency": "monthly",
  "currency": "USD",
  "price_amount": "19.00",
  "teams_limit_type": "limited",
  "teams_count": 1,
  "players_limit_type": "limited",
  "players_count": 15,
  "historical_records_duration": "1_month",
  "is_active": true,
  "include_offline_sync": false,
  "description": "Suitable for individual coaches.",
  "features": [
    "Manage 1 Team",
    "Add up to 15 Players",
    "Online Practice Session Recording",
    "Basic Player Statistics",
    "Team Leaderboard",
    "Historical Records (Last 1 Month)"
  ]
}
```

For coach plans, do **not** send `coaches_limit_type` or `coaches_count`.

---

## API endpoints

### GET `/super-admin/subscription-plans/currencies`

Returns Stripe-supported currencies for the create-plan dropdown.

### GET `/super-admin/subscription-plans`

List plans for a specific role with pagination, **Active / Archived** categories, and optional filters.

Query params:

| Param | Type | Required | Description |
|---|---|---|---|
| `role` | `org_admin` \| `coach` | **Yes** | Which subscription section to load |
| `status` | `active` \| `archived` | No | Plan category. Omit to return both |
| `page` | int | No | Default `1` |
| `page_size` | int | No | Default `20`, max `100` |
| `billing_frequency` | `monthly` \| `yearly` | No | Optional filter |
| `is_active` | boolean | No | Deprecated. Use `status` instead |
| `search` | string | No | Search name/description |

#### Categories

| `status` | Meaning |
|---|---|
| `active` | Plan is available for new Stripe customers (`is_active=true` and not archived) |
| `archived` | Plan is archived in Stripe for new customers. Existing subscribers may still be on it |

The response also includes:

- `status` — local category (`active` or `archived`)
- `stripe_status` — live Stripe product **and** price `active` flags (`active`, `archived`, or `null` if Stripe is unavailable)
- `counts.active` / `counts.archived` — tab counts for the same `role` (and other filters except `status`)

Before listing, the backend syncs local plan status with Stripe:

- If the Stripe product or price is inactive, the local plan is marked archived
- If the local plan is archived but Stripe is still active, the Stripe product/price are archived

#### Examples

Active organization admin plans:

```text
GET /api/v1/super-admin/subscription-plans?role=org_admin&status=active&page=1&page_size=20
```

Archived coach plans:

```text
GET /api/v1/super-admin/subscription-plans?role=coach&status=archived&page=1&page_size=20
```

All coach plans (both categories):

```text
GET /api/v1/super-admin/subscription-plans?role=coach&page=1&page_size=20
```

#### Example response

```json
{
  "items": [
    {
      "id": "11111111-2222-3333-4444-555555555555",
      "role": "coach",
      "name": "Starter Plan",
      "billing_frequency": "monthly",
      "currency": "USD",
      "price_amount": "19.00",
      "stripe_product_id": "prod_xxx",
      "stripe_price_id": "price_xxx",
      "is_active": true,
      "status": "active",
      "stripe_status": "active",
      "archived_at": null,
      "replacement_plan_id": null
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 1,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  },
  "counts": {
    "active": 1,
    "archived": 2
  }
}
```

### GET `/super-admin/subscription-plans/{plan_id}`

Fetch one plan scoped to a role.

Query params:

| Param | Type | Required | Description |
|---|---|---|---|
| `role` | `org_admin` \| `coach` | **Yes** | Must match the plan's role |

Example:

```text
GET /api/v1/super-admin/subscription-plans/{plan_id}?role=org_admin
```

Returns `404` if the plan exists but belongs to the other role.

### POST `/super-admin/subscription-plans`

Create a plan.

On success, the backend:

1. Creates a Stripe Product
2. Creates a Stripe recurring Price
3. Stores both IDs in `subscription_plans_staging`

Active Stripe subscriber records are stored separately in `stripe_subscriptions_staging` (not the client-owned `subscriptions` table).

### PUT `/super-admin/subscription-plans/{plan_id}`

Update a plan scoped to a role.

Required query param:

| Param | Type | Required | Description |
|---|---|---|---|
| `role` | `org_admin` \| `coach` | **Yes** | Must match the plan's role |

Example:

```text
PUT /api/v1/super-admin/subscription-plans/{plan_id}?role=org_admin
```

#### Immutable fields after creation

The backend rejects changes to:

- `role`
- `currency`
- `billing_frequency`

Frontend edit form should disable these fields once a plan exists.

#### Price change behavior

When `price_amount` changes:

1. Backend creates a **new** Stripe Price on the same Product
2. Old Stripe Price is archived (`active=false`)
3. All active subscribers are migrated to the new price in Stripe
4. Each subscriber receives a price-change email
5. Local `stripe_price_id` and `price_amount` are updated

Example update payload:

```json
{
  "name": "Starter Plan",
  "price_amount": "59.00",
  "teams_limit_type": "limited",
  "teams_count": 3,
  "coaches_limit_type": "limited",
  "coaches_count": 3,
  "players_limit_type": "limited",
  "players_count": 45,
  "historical_records_duration": "3_months",
  "is_active": true,
  "include_offline_sync": true,
  "description": "Updated description",
  "features": ["Online Practice Session Recording"]
}
```

If the frontend accidentally sends `currency` or `billing_frequency` with a different value, the API returns:

```json
{
  "success": false,
  "error": {
    "code": "IMMUTABLE_FIELD",
    "message": "Currency cannot be changed after plan creation",
    "details": null
  }
}
```

### DELETE `/super-admin/subscription-plans/{plan_id}`

Archives the plan. The URL stays as DELETE so the current admin frontend does not need to change.

Query params:

| Param | Type | Required | Description |
|---|---|---|---|
| `role` | `org_admin` \| `coach` | **Yes** | Must match the plan's role |
| `replacement_plan_id` | UUID | No | Active plan to move existing subscribers to at period end |

Example:

```text
DELETE /api/v1/super-admin/subscription-plans/{plan_id}?role=coach
DELETE /api/v1/super-admin/subscription-plans/{plan_id}?role=coach&replacement_plan_id={new_plan_id}
```

What archive does:

1. Sets `is_active=false` and `archived_at` (the plan is **not** deleted)
2. Deactivates the Stripe product/price so **new customers cannot subscribe**
3. Existing subscribers keep the current plan until their billing period ends
4. At period end, Stripe auto-migrates them to a replacement plan when one is available
5. Each purchased user is emailed about the archive

Replacement plan selection:

- If `replacement_plan_id` is sent, that plan is used (same role, currency, and billing frequency required)
- If omitted, the backend looks for another **active** plan with the same `role`, `name`, and `billing_frequency`
- If none exists, current subscribers stay on the archived price until they cancel

Response:

```json
{
  "message": "Subscription plan archived successfully."
}
```

---

## Deployment note — `include_offline_sync` column

`include_offline_sync` is a DB column added via an auto-migration that runs at server startup (`run_subscription_schema_migrations`).

**After deploying this change you must restart the server** (PM2: `pm2 restart hoops-engine-api-7770`) so that:

1. The `ALTER TABLE subscription_plans_staging ADD COLUMN include_offline_sync ...` migration runs and the column is created in the DB.
2. SQLAlchemy loads the updated model that includes the column, so it is SELECTed on every GET request.

Plans created or fetched **before the restart** will not return `include_offline_sync` in the response. After restart, existing plans return `false` (the column default) and new/updated plans reflect the value you send.

---

## Plan response shape

```json
{
  "id": "11111111-2222-3333-4444-555555555555",
  "role": "org_admin",
  "name": "Starter Plan",
  "billing_frequency": "monthly",
  "currency": "USD",
  "price_amount": "49.00",
  "stripe_product_id": "prod_xxx",
  "stripe_price_id": "price_xxx",
  "teams_limit_type": "limited",
  "teams_count": 3,
  "coaches_limit_type": "limited",
  "coaches_count": 3,
  "players_limit_type": "limited",
  "players_count": 45,
  "historical_records_duration": "3_months",
  "is_active": true,
  "include_offline_sync": false,
  "archived_at": null,
  "replacement_plan_id": null,
  "description": "Suitable for small basketball academies.",
  "features": ["Online Practice Session Recording"],
  "created_at": "2026-08-18T10:00:00.000000Z",
  "updated_at": "2026-08-18T10:00:00.000000Z"
}
```

---

## Stripe webhook setup

Create a webhook endpoint in Stripe Dashboard:

```text
https://YOUR_API_DOMAIN/api/v1/webhooks/stripe
```

Recommended events:

- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_failed`

The webhook endpoint verifies the `Stripe-Signature` header using `STRIPE_WEBHOOK_SECRET`.

When creating Stripe subscriptions from the frontend/checkout flow later, include metadata so the backend can link them locally:

```json
{
  "metadata": {
    "plan_id": "11111111-2222-3333-4444-555555555555",
    "subscriber_email": "user@example.com",
    "subscriber_user_id": "22222222-3333-4444-5555-666666666666"
  }
}
```

---

## Frontend UI rules

The admin panel should have **two separate subscription sections**:

1. **Organization Admin Subscriptions** — always use `role=org_admin`
2. **Coach Subscriptions** — always use `role=coach`

Inside each section, use two list tabs:

1. **Active** — `GET /super-admin/subscription-plans?role=...&status=active`
2. **Archived** — `GET /super-admin/subscription-plans?role=...&status=archived`

Use `counts.active` and `counts.archived` for tab badges. Compare `status` (local) with `stripe_status` if you need to show a Stripe mismatch.

### Create plan modal

- Set `role` from the active admin tab (`org_admin` or `coach`)
- Show `currency` dropdown from `/currencies`
- Show `billing_frequency` dropdown (`monthly`, `yearly`)
- For `role=org_admin`, show Teams, Coaches, Players limits
- For `role=coach`, show Teams and Players only
- When a limit dropdown is `unlimited`, hide/disable the count field and send `null`
- Features list is dynamic (`+ Add New Feature`)
- Show an **Include Offline Sync** checkbox (`include_offline_sync`, default unchecked). When checked, "Offline Recording & Auto Sync" is treated as a plan feature

### Edit plan modal

Disable/read-only:

- `role`
- `currency`
- `billing_frequency`

Pass the current tab's `role` as a query param on get/update/delete requests.

Editable:

- `name`
- `price_amount`
- limits
- `historical_records_duration`
- `is_active`
- `include_offline_sync`
- `description`
- `features`

Show a confirmation dialog when price changes, explaining that existing subscribers will be migrated and emailed.

---

## Error codes

| Code | Meaning |
|---|---|
| `STRIPE_NOT_CONFIGURED` | Stripe env vars missing |
| `IMMUTABLE_FIELD` | Tried to change role, currency, or billing frequency |
| `PLAN_NOT_FOUND` | Plan does not exist for the specified role |
| `PLAN_HAS_ACTIVE_SUBSCRIPTIONS` | Unused for archive (kept for compatibility) |
| `VALIDATION_ERROR` | Invalid limits or payload |
| `INVALID_STRIPE_SIGNATURE` | Webhook signature failed |

---

## Server deployment checklist

1. Add Stripe env vars to `.env`
2. `pip install -r requirements.txt`
3. Restart PM2
4. Create webhook in Stripe Dashboard
5. Test with Swagger `/docs`
6. Create plans from admin UI

Example PM2 restart:

```bash
cd /var/www/html/hoops-engine-api
source venv/bin/activate
pip install -r requirements.txt
deactivate
pm2 restart hoops-engine-api-7770
```

---

## Notes

- Prices are stored in cents internally and returned as decimals in API responses.
- Ultimate plans are expected to use `billing_frequency: "yearly"` in the admin UI.
- PDF/Excel export modules are product-scope decisions; the plan APIs only store feature text.
- Subscriber migration on **price edit** is immediate (`STRIPE_PRICE_MIGRATION_PRORATION_BEHAVIOR=none`).
- Subscriber migration on **plan archive** happens at the **end of the current billing period**.
