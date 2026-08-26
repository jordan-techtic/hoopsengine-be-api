# Auth API Integration

Base URL for local development:

```
http://127.0.0.1:8000/api/v1
```

Swagger UI: `http://127.0.0.1:8000/docs`

All auth endpoints use:

- **Content-Type:** `application/json`
- **Accept:** `application/json`

---

## Login

Authenticate a user with email and password.

### Endpoint

```
POST /auth/login
```

### Request body

| Field      | Type   | Required | Description        |
|------------|--------|----------|--------------------|
| `email`    | string | Yes      | User email address |
| `password` | string | Yes      | User password      |

### Example request

```json
{
  "email": "admin.hoopsengine@yopmail.com",
  "password": "Admin@123"
}
```

### Success response — `200 OK`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in_hours": 24,
  "user": {
    "id": "a752feb1-7852-4a3e-9d07-2628b9873cb1",
    "email": "admin.hoopsengine@yopmail.com",
    "role": "super_admin",
    "org_id": null,
    "first_name": "Super",
    "last_name": "Admin",
    "is_super_admin": true,
    "is_active": true,
    "last_sign_in_at": "2026-08-17T06:07:58.460608Z"
  }
}
```

### Response fields

| Field               | Type    | Description                                      |
|---------------------|---------|--------------------------------------------------|
| `access_token`      | string  | JWT token for authenticated requests             |
| `token_type`        | string  | Always `bearer`                                  |
| `expires_in_hours`  | number  | Token validity in hours                          |
| `user.id`           | string  | User UUID                                        |
| `user.email`        | string  | User email                                       |
| `user.role`         | string  | User role (see roles below)                      |
| `user.org_id`       | string  | Organization UUID, or `null`                     |
| `user.first_name`   | string  | First name, or `null`                            |
| `user.last_name`    | string  | Last name, or `null`                             |
| `user.is_super_admin` | boolean | Whether user is a super admin                  |
| `user.is_active`    | boolean | Whether the account is active                    |
| `user.last_sign_in_at` | string | ISO 8601 timestamp of last login, or `null`   |

### User roles

| Value         | Description   |
|---------------|---------------|
| `super_admin` | Super admin   |
| `org_admin`   | Org admin     |
| `coach`       | Coach         |
| `player`      | Player        |

### Error response — `401 Unauthorized`

```json
{
  "success": false,
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Invalid email or password",
    "details": null
  }
}
```

---

## Using the access token

Send the JWT on protected API requests:

```
Authorization: Bearer <access_token>
```

Example:

```http
GET /api/v1/some-protected-route
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Token expiry is controlled by backend config (`ACCESS_TOKEN_EXPIRE_HOURS`, default `24`).

---

## Logout

Invalidate the current user session. Works for all roles (`super_admin`, `org_admin`, `coach`, `player`).

Requires the same JWT used for login. After logout, the token can no longer be used on protected routes.

### Endpoint

```
POST /auth/logout
```

### Headers

```
Authorization: Bearer <access_token>
```

No request body required.

### Success response — `200 OK`

```json
{
  "message": "Logged out successfully"
}
```

### Error response — `401 Unauthorized`

Missing or invalid token:

```json
{
  "success": false,
  "error": {
    "code": "MISSING_TOKEN",
    "message": "Could not validate credentials",
    "details": null
  }
}
```

Token already logged out:

```json
{
  "success": false,
  "error": {
    "code": "TOKEN_REVOKED",
    "message": "Session has expired or been logged out",
    "details": null
  }
}
```

---

## Forgot password

Request a password reset for an email address.

### Endpoint

```
POST /auth/forgot-password
```

### Request body

```json
{
  "email": "admin.hoopsengine@yopmail.com"
}
```

### Success response — `200 OK`

```json
{
  "message": "Password reset link has been sent to your email.",
  "reset_token": null
}
```

### Error response — `404 Not Found`

Returned when no active account exists for the given email.

```json
{
  "success": false,
  "error": {
    "code": "USER_NOT_FOUND",
    "message": "We couldn't find an account with that email. Please check the address and try again.",
    "details": null
  }
}
```

Notes:

- In `DEBUG` mode only, `reset_token` may be included in the success response for local testing.
- When SendGrid is configured, a password reset email is sent with a link like:
  `http://localhost:5173/reset-password?token=<reset_token>`
  (configured via `RESET_PASSWORD_URL` in backend `.env`).
- The email includes a clear message and a **Reset Password** button for the user.

---

## Validate reset token

Check whether the reset token from the email link is valid before showing the reset password form.

Call this when the user lands on `/reset-password?token=...`.

### Endpoint

```
POST /auth/validate-reset-token
```

### Request body

| Field   | Type   | Required | Description                              |
|---------|--------|----------|------------------------------------------|
| `token` | string | Yes      | Reset token from the email link query param |

### Example request

```json
{
  "token": "A7ms2FsT-sGzC4HjcdIRQoacF7sHvlWIAIG7vLK_0b0"
}
```

### Valid token response — `200 OK`

```json
{
  "valid": true,
  "message": "Reset link is valid. You can set a new password.",
  "email": "admin.hoopsengine@yopmail.com"
}
```

### Invalid or expired token response — `200 OK`

```json
{
  "valid": false,
  "message": "This reset link is invalid or has expired. Please request a new password reset.",
  "email": null
}
```

Notes:

- Both valid and invalid tokens return HTTP `200`.
- Use the `valid` field to decide whether to show the reset password form.
- If `valid` is `true`, `email` confirms which account will be updated.

### Recommended frontend flow

1. User opens `http://localhost:5173/reset-password?token=...`
2. Frontend reads `token` from the URL
3. Call `POST /auth/validate-reset-token`
4. If `valid === true`, show the new password form
5. Submit `POST /auth/reset-password` with the same token

---

## Reset password

Set a new password using the reset token.

### Endpoint

```
POST /auth/reset-password
```

### Request body

| Field          | Type   | Required | Description                          |
|----------------|--------|----------|--------------------------------------|
| `token`        | string | Yes      | Reset token from forgot-password     |
| `new_password` | string | Yes      | New password (8–72 characters)       |

### Example request

```json
{
  "token": "A7ms2FsT-sGzC4HjcdIRQoacF7sHvlWIAIG7vLK_0b0",
  "new_password": "NewPassword@123"
}
```

### Success response — `200 OK`

```json
{
  "message": "Password has been reset successfully"
}
```

### Error response — `400 Bad Request`

```json
{
  "success": false,
  "error": {
    "code": "INVALID_RESET_TOKEN",
    "message": "Invalid or expired reset token",
    "details": null
  }
}
```

---

## Standard error format

All auth errors follow this structure:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": null
  }
}
```

Common auth error codes:

| HTTP Status | Code                  | When it happens                    |
|-------------|-----------------------|------------------------------------|
| 401         | `INVALID_CREDENTIALS` | Wrong email or password on login |
| 404         | `USER_NOT_FOUND`      | Email not found on forgot password |
| 401         | `TOKEN_REVOKED`       | Logged out or invalidated token  |
| 400         | `INVALID_RESET_TOKEN` | Invalid or expired reset token     |
| 401         | `INVALID_TOKEN`       | Missing or invalid JWT           |
| 401         | `MISSING_TOKEN`       | Authorization header missing     |
| 422         | `VALIDATION_ERROR`    | Invalid request body             |
| 500         | `DATABASE_ERROR`      | Database error                   |
| 500         | `INTERNAL_SERVER_ERROR` | Unexpected server error        |

Validation error example — `422 Unprocessable Entity`:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "type": "missing",
        "loc": ["body", "email"],
        "msg": "Field required",
        "input": {}
      }
    ]
  }
}
```

---

## Frontend example (fetch)

```javascript
const API_BASE = "http://127.0.0.1:8000/api/v1";

export async function login(email, password) {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ email, password }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.error?.message || "Login failed");
  }

  return data;
}

// Usage
const result = await login("admin.hoopsengine@yopmail.com", "Admin@123");

localStorage.setItem("access_token", result.access_token);
localStorage.setItem("user", JSON.stringify(result.user));

export async function logout() {
  const token = localStorage.getItem("access_token");

  const response = await fetch(`${API_BASE}/auth/logout`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
  });

  const data = await response.json();

  localStorage.removeItem("access_token");
  localStorage.removeItem("user");

  if (!response.ok) {
    throw new Error(data?.error?.message || "Logout failed");
  }

  return data;
}

export async function validateResetToken(token) {
  const response = await fetch(`${API_BASE}/auth/validate-reset-token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ token }),
  });

  return response.json();
}

// On /reset-password page load:
// const token = new URLSearchParams(window.location.search).get("token");
// const result = await validateResetToken(token);
// if (!result.valid) showExpiredLinkMessage(result.message);
// else showResetPasswordForm(result.email, token);
```

Authenticated request example:

```javascript
const token = localStorage.getItem("access_token");

const response = await fetch(`${API_BASE}/some-protected-route`, {
  headers: {
    Authorization: `Bearer ${token}`,
    Accept: "application/json",
  },
});
```
