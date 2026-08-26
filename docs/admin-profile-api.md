# Super Admin Profile API

This API lets a super admin view and update their profile (name, email, and profile image).

Password changes are **not** handled here — use the existing forgot/reset password flow from the auth API.

Base path:

```text
/api/v1/super-admin/profile
```

All endpoints require a bearer token for a `super_admin` user.

---

## Swagger UI (testing)

You can test these endpoints directly in Swagger UI:

1. Open `http://<host>:<port>/docs`
2. Click **Authorize** and paste your JWT access token (same token you get from `/api/v1/auth/login`)
3. In the endpoint list, open the **super-admin-profile** tag
4. Use **Try it out** for:
   - `GET /super-admin/profile`
   - `PUT /super-admin/profile` (multipart form fields: `name`, `email`, `profile_image`, `remove_profile_image`)
   - `GET /super-admin/profile/avatar` (returns an image file; Swagger may display it as a download/response depending on browser)

---

## GET `/super-admin/profile`

Fetch the authenticated super admin profile.

### Headers

```http
Authorization: Bearer <access_token>
Accept: application/json
```

### Example response — `200 OK`

```json
{
  "id": "a752feb1-7852-4a3e-9d07-2628b9873cb1",
  "name": "Super Admin",
  "email": "admin.hoopsengine@yopmail.com",
  "profile_image": {
    "url": "/api/v1/super-admin/profile/avatar",
    "original_name": "avatar.png",
    "content_type": "image/png"
  },
  "updated_at": "2026-08-19T10:00:00.000000Z"
}
```

When no profile image has been uploaded, `profile_image` is `null`.

### Response fields

| Field | Type | Description |
|---|---|---|
| `id` | string (UUID) | Super admin user ID |
| `name` | string | Display name shown in the profile UI |
| `email` | string | Account email |
| `profile_image` | object \| null | Image metadata when an avatar exists |
| `profile_image.url` | string | Relative URL to fetch the avatar file |
| `profile_image.original_name` | string | Original uploaded filename |
| `profile_image.content_type` | string | MIME type (e.g. `image/png`) |
| `updated_at` | string | ISO 8601 timestamp of last profile update |

### Error responses

`401 Unauthorized` — missing or invalid JWT

`403 Forbidden` — user is not a super admin

---

## PUT `/super-admin/profile`

Update the authenticated super admin profile.

Send as **`multipart/form-data`**. Include only the fields you want to change.

### Headers

```http
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
Accept: application/json
```

### Form fields

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | No | Display name (e.g. `Super Admin`) |
| `email` | string | No | New email address |
| `profile_image` | file | No | Profile image file (JPG, JPEG, or PNG — max 2 MB) |
| `remove_profile_image` | boolean | No | Set to `true` to remove the current avatar |

At least one of `name`, `email`, `profile_image`, or `remove_profile_image=true` must be provided.

### Profile image rules

- Allowed types: **JPG**, **JPEG**, **PNG**
- Max size: **2 MB**
- Uploading a new image replaces the previous one

### Example — update name and email (no image)

```http
PUT /api/v1/super-admin/profile
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

name=Super Admin
email=admin.hoopsengine@yopmail.com
```

### Example — update with profile image (JavaScript)

```javascript
const formData = new FormData();
formData.append("name", "Super Admin");
formData.append("email", "admin.hoopsengine@yopmail.com");
formData.append("profile_image", fileInput.files[0]);

const response = await fetch("http://127.0.0.1:8000/api/v1/super-admin/profile", {
  method: "PUT",
  headers: {
    Authorization: `Bearer ${accessToken}`,
  },
  body: formData,
});
```

### Example response — `200 OK`

```json
{
  "message": "Profile updated successfully.",
  "profile": {
    "id": "a752feb1-7852-4a3e-9d07-2628b9873cb1",
    "name": "Super Admin",
    "email": "admin.hoopsengine@yopmail.com",
    "profile_image": {
      "url": "/api/v1/super-admin/profile/avatar",
      "original_name": "avatar.png",
      "content_type": "image/png"
    },
    "updated_at": "2026-08-19T10:05:00.000000Z"
  }
}
```

### Error responses

`400 Bad Request` — invalid image type or file too large

```json
{
  "success": false,
  "error": {
    "code": "INVALID_PROFILE_IMAGE_TYPE",
    "message": "Unsupported profile image type. Allowed files: JPG, JPEG, PNG.",
    "details": null
  }
}
```

```json
{
  "success": false,
  "error": {
    "code": "PROFILE_IMAGE_TOO_LARGE",
    "message": "Profile image size must be 2 MB or less",
    "details": null
  }
}
```

`409 Conflict` — email already used by another account

```json
{
  "success": false,
  "error": {
    "code": "EMAIL_ALREADY_IN_USE",
    "message": "This email is already in use by another account",
    "details": null
  }
}
```

`422 Unprocessable Entity` — validation error (e.g. empty name or no fields sent)

---

## GET `/super-admin/profile/avatar`

Download the authenticated super admin profile image file.

Use the `profile_image.url` from the profile response. Prepend your API base URL when rendering in the frontend.

### Headers

```http
Authorization: Bearer <access_token>
```

### Example

```http
GET /api/v1/super-admin/profile/avatar
Authorization: Bearer <access_token>
```

Returns the image file with the appropriate `Content-Type` header.

`404 Not Found` — no profile image uploaded or file missing on disk

---

## Frontend integration notes

### Profile Management page flow

1. On page load, call **GET** `/super-admin/profile` with the super admin JWT.
2. Bind `name` and `email` to the form fields.
3. If `profile_image` is present, load the avatar from:
   `{API_BASE_URL}{profile_image.url}` with the same JWT in the `Authorization` header.
4. For initials fallback (e.g. **SA**), derive from `name` when `profile_image` is `null`.
5. On **Save Changes**, call **PUT** `/super-admin/profile` with `multipart/form-data`.
6. **Reset Password** should link to the existing forgot/reset password UI — do not send password in the profile update request.

### Displaying the avatar in `<img>`

Because the avatar endpoint requires authentication, either:

- Fetch the image with `fetch` + `Authorization` header, convert to a blob URL, and set `img.src`, or
- Use your app's authenticated API client that supports binary responses.

Example:

```javascript
async function loadAvatar(accessToken, apiBaseUrl) {
  const res = await fetch(`${apiBaseUrl}/super-admin/profile/avatar`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) return null;
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}
```

### After email change

The JWT still contains the old email in its payload until it expires or the user logs in again. The updated email is returned in the profile response and will be used on the next login.

---

## Environment variables

Optional overrides in `.env`:

| Variable | Default | Description |
|---|---|---|
| `PROFILE_IMAGE_UPLOAD_DIR` | `storage/profile_images` | Directory for stored profile images |
| `PROFILE_IMAGE_MAX_SIZE_MB` | `2` | Max upload size in megabytes |
