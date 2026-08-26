# Super Admin Users API

This API lets a super admin list, create, update, and remove user accounts on the Manage Users page (coaches and players, plus other roles).

Base path:

```text
/api/v1/super-admin/users
```

All endpoints require a bearer token for a `super_admin` user. Passwords are write-only and are never returned.

---

## Swagger UI (testing)

1. Open `http://<host>:<port>/docs`
2. Click **Authorize** and paste the JWT from `POST /api/v1/auth/login`
3. Open the **admin-users** tag
4. Use **Try it out** for:
   - `GET /super-admin/users`
   - `POST /super-admin/users`
   - `PUT /super-admin/users/{user_id}`
   - `DELETE /super-admin/users/{user_id}`

---

## Roles

| Value | Label |
|---|---|
| `coach` | Coach |
| `player` | Player |
| `org_admin` | Organization Admin |
| `super_admin` | Super Admin |

The API also accepts display labels such as `Coach` and `Player`.

Password rules: at least 8 characters, one uppercase, one lowercase, one number, and one special character.

---

## GET `/super-admin/users`

Paginated list for the users table. `is_self` is `true` on the signed-in super admin so the UI can disable Remove.

### Query parameters

| Name | Type | Default | Description |
|---|---|---|---|
| `page` | integer | `1` | 1-based page number |
| `page_size` | integer | `20` | Items per page (1–100) |
| `role` | string | omitted | Filter by `coach`, `player`, `org_admin`, or `super_admin` |
| `search` | string | omitted | Optional filter on name or email |

### Example response — `200 OK`

```json
{
  "items": [
    {
      "id": "11111111-2222-3333-4444-555555555555",
      "first_name": "John",
      "last_name": "Doe",
      "name": "John Doe",
      "email": "john.doe@example.com",
      "role": "coach",
      "roles": ["coach"],
      "description": null,
      "org_id": null,
      "is_super_admin": false,
      "is_active": true,
      "is_self": false,
      "last_sign_in_at": null,
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
  },
  "roles": [
    {"value": "coach", "label": "Coach", "description": "Coach account"},
    {"value": "player", "label": "Player", "description": "Player account"},
    {"value": "org_admin", "label": "Organization Admin", "description": "Organization administrator"},
    {"value": "super_admin", "label": "Super Admin", "description": "Platform super administrator"}
  ]
}
```

When there are no users, `items` is `[]` and `pagination.total` is `0`.

### Error responses

`401 Unauthorized` — missing or invalid JWT (`MISSING_TOKEN`, `INVALID_TOKEN`, `TOKEN_REVOKED`)

`403 Forbidden` — user is not a super admin (`FORBIDDEN`)

---

## POST `/super-admin/users`

Create a user.

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `first_name` | string | Yes | First name |
| `last_name` | string | Yes | Last name |
| `name` | string | No | Full name (optional; returned on responses) |
| `email` | string (email) | Yes | Unique login email |
| `password` | string | Yes | Initial password |
| `role` | string | Yes | `coach`, `player`, `org_admin`, or `super_admin` |
| `org_id` | UUID | No | Organization to attach |

```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john.doe@example.com",
  "password": "Coach@123",
  "role": "coach"
}
```

### Example response — `200 OK`

```json
{
  "message": "User created successfully.",
  "id": "11111111-2222-3333-4444-555555555555",
  "first_name": "John",
  "last_name": "Doe",
  "name": "John Doe",
  "email": "john.doe@example.com",
  "role": "coach",
  "roles": ["coach"],
  "description": null,
  "org_id": null,
  "is_super_admin": false,
  "is_active": true,
  "is_self": false,
  "last_sign_in_at": null,
  "created_at": "2026-08-26T10:00:00.000000Z"
}
```

### Error responses

`400 Bad Request` — weak password or invalid fields (`VALIDATION_ERROR`)

`409 Conflict` — duplicate email (`EMAIL_ALREADY_IN_USE`)

`401` / `403` / `422` — as above

---

## PUT `/super-admin/users/{user_id}`

Partially update a user. Password is optional.

### Error responses

`400` — invalid data (`VALIDATION_ERROR`)

`404 Not Found` — unknown or already-removed id (`USER_NOT_FOUND`)

`409 Conflict` — duplicate email (`EMAIL_ALREADY_IN_USE`)

Success body matches POST (message: `User updated successfully.`).

---

## DELETE `/super-admin/users/{user_id}`

Soft-delete a user. The signed-in super admin cannot remove their own account.

### Example response — `200 OK`

```json
{
  "message": "User removed successfully."
}
```

### Error responses

`400 Bad Request` — attempting to delete yourself (`CANNOT_DELETE_SELF`)

`404 Not Found` — unknown id (`USER_NOT_FOUND`)

`401` / `403` — as above
