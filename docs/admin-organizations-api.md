# Super Admin Organizations API

This API lets a super admin list, create, update, and remove organizations on the Manage Organizations page.

Base path:

```text
/api/v1/super-admin/organizations
```

All endpoints require a bearer token for a `super_admin` user.

Contact email is stored as `admin_email` on the `organizations` table. The API exposes it as `contact_email` and `email`. Phone is returned as both `phone_number` and `phone`.

---

## Swagger UI (testing)

1. Open `http://<host>:<port>/docs`
2. Click **Authorize** and paste the JWT from `POST /api/v1/auth/login`
3. Open the **super-admin-organizations** tag
4. Use **Try it out** for:
   - `GET /super-admin/organizations`
   - `POST /super-admin/organizations`
   - `PUT /super-admin/organizations/{organization_id}`
   - `DELETE /super-admin/organizations/{organization_id}`

---

## GET `/super-admin/organizations`

Paginated list for the organizations table (name, contact email, phone, actions).

### Query parameters

| Name | Type | Default | Description |
|---|---|---|---|
| `page` | integer | `1` | 1-based page number |
| `page_size` | integer | `20` | Items per page (1–100) |
| `search` | string | omitted | Optional filter on name, email, or phone |

### Headers

```http
Authorization: Bearer <access_token>
Accept: application/json
```

### Example response — `200 OK`

```json
{
  "items": [
    {
      "id": "11111111-2222-3333-4444-555555555555",
      "name": "Organization Name",
      "organization": "Organization Name",
      "contact_email": "contact@example.com",
      "email": "contact@example.com",
      "phone_number": "1234567890",
      "phone": "1234567890",
      "address": "123 Main St",
      "description": null,
      "join_code": "A1B2C3D4",
      "created_at": "2026-08-26T10:00:00.000000Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 1,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

When there are no organizations, `items` is `[]` and `pagination.total` is `0`.

### Error responses

`401 Unauthorized` — missing or invalid JWT (`MISSING_TOKEN`, `INVALID_TOKEN`, `TOKEN_REVOKED`)

`403 Forbidden` — user is not a super admin (`FORBIDDEN`)

---

## POST `/super-admin/organizations`

Create an organization.

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Organization name |
| `contact_email` | string (email) | Yes | Contact email |
| `phone_number` | string | Yes | Phone number |
| `address` | string | Yes | Street address |

```json
{
  "name": "Organization Name",
  "contact_email": "contact@example.com",
  "phone_number": "1234567890",
  "address": "123 Main St"
}
```

### Example response — `200 OK`

```json
{
  "message": "Organization created successfully.",
  "id": "11111111-2222-3333-4444-555555555555",
  "name": "Organization Name",
  "organization": "Organization Name",
  "contact_email": "contact@example.com",
  "email": "contact@example.com",
  "phone_number": "1234567890",
  "phone": "1234567890",
  "address": "123 Main St",
  "description": null,
  "join_code": "A1B2C3D4",
  "created_at": "2026-08-26T10:00:00.000000Z"
}
```

### Error responses

`400 Bad Request` — invalid name, phone, or address (`VALIDATION_ERROR`)

`401` / `403` — same as list

`409 Conflict` — unique constraint failure (`ORGANIZATION_CREATE_FAILED`)

`422 Unprocessable Entity` — schema validation failed (`VALIDATION_ERROR`), including invalid email format

---

## PUT `/super-admin/organizations/{organization_id}`

Partially update an organization. Send only fields to change.

### Error responses

`400` — no fields provided, or invalid name/phone/address (`VALIDATION_ERROR`)

`404 Not Found` — unknown id (`ORGANIZATION_NOT_FOUND`)

`401` / `403` / `422` — as above

Success body matches POST (message: `Organization updated successfully.`).

---

## DELETE `/super-admin/organizations/{organization_id}`

Remove an organization after the UI confirmation modal.

### Example response — `200 OK`

```json
{
  "message": "Organization removed successfully."
}
```

### Error responses

`404 Not Found` — unknown id (`ORGANIZATION_NOT_FOUND`)

`409 Conflict` — related teams, coaches, players, or session data still exist (`ORGANIZATION_HAS_DEPENDENCIES`)

`401` / `403` — as above
