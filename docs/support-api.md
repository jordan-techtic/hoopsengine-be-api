# Support Request API

This API lets users submit support requests with an optional attachment, and lets super admins fetch submitted requests.

Base path:

```text
/api/v1/support-requests
```

## POST `/support-requests`

Submit a support request.

### Content type

```text
multipart/form-data
```

### Form fields

| Field | Type | Required | Description |
|---|---|---|---|
| `email` | string | Yes | User email address |
| `name` | string | Yes | User full name |
| `subject` | string | Yes | Support request subject |
| `message` | string | Yes | Support request details |
| `attachment` | file | No | Optional file up to 5 MB |

### Allowed attachment types

- Images: `JPG`, `JPEG`, `PNG`, `WEBP`
- Documents: `PDF`, `DOC`, `DOCX`
- Spreadsheets: `XLS`, `XLSX`
- Text: `TXT`

### Example response — `200 OK`

```json
{
  "message": "Your support request has been submitted successfully.",
  "request_id": "11111111-2222-3333-4444-555555555555"
}
```

### Error responses

`400 Bad Request`

```json
{
  "success": false,
  "error": {
    "code": "INVALID_ATTACHMENT_TYPE",
    "message": "Unsupported attachment type. Allowed files: JPG, JPEG, PNG, WEBP, PDF, DOC, DOCX, XLS, XLSX, TXT.",
    "details": null
  }
}
```

`400 Bad Request`

```json
{
  "success": false,
  "error": {
    "code": "ATTACHMENT_TOO_LARGE",
    "message": "Attachment size must be 5 MB or less",
    "details": null
  }
}
```

## GET `/support-requests`

Fetch submitted support requests.

This endpoint requires a bearer token for a `super_admin` user.

### Query params

| Field | Type | Required | Description |
|---|---|---|---|
| `page` | integer | No | Page number (1-based), default `1` |
| `page_size` | integer | No | Items per page, default `20`, max `100` |
| `search` | string | No | Search by email, name, subject, or message (case-insensitive) |

### Example request

```http
GET /api/v1/support-requests?page=1&page_size=20&search=login
Authorization: Bearer <access_token>
```

### Example response — `200 OK`

```json
{
  "items": [
    {
      "id": "11111111-2222-3333-4444-555555555555",
      "email": "user@example.com",
      "name": "John Doe",
      "subject": "Unable to login",
      "message": "I am not able to log in to the app.",
      "created_at": "2026-08-17T08:30:00.000000Z",
      "attachment": {
        "original_name": "screenshot.png",
        "content_type": "image/png",
        "size_bytes": 245812,
        "download_url": "/api/v1/support-requests/11111111-2222-3333-4444-555555555555/attachment"
      }
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

### Pagination fields

| Field | Description |
|---|---|
| `page` | Current page number |
| `page_size` | Number of items per page |
| `total` | Total matching items (after search filter) |
| `total_pages` | Total number of pages |
| `has_next` | `true` if another page exists after the current one |
| `has_prev` | `true` if a page exists before the current one |

## GET `/support-requests/{request_id}/attachment`

Download the attachment for a support request.

This endpoint requires a bearer token for a `super_admin` user.

### Path params

| Field | Type | Required | Description |
|---|---|---|---|
| `request_id` | UUID | Yes | Support request ID |

### Example request

```http
GET /api/v1/support-requests/11111111-2222-3333-4444-555555555555/attachment
Authorization: Bearer <access_token>
```

### Success response — `200 OK`

Returns the file as binary content with headers:

```http
Content-Type: image/png
Content-Disposition: attachment; filename="screenshot.png"
```

### Frontend download example

Use the `download_url` from the list response and send the JWT in the `Authorization` header:

```javascript
async function downloadSupportAttachment(downloadUrl, accessToken, filename) {
  const response = await fetch(`${API_BASE_URL}${downloadUrl}`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    throw new Error("Failed to download attachment");
  }

  const blob = await response.blob();
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(objectUrl);
}
```

### Error response — `404 Not Found`

```json
{
  "success": false,
  "error": {
    "code": "ATTACHMENT_NOT_FOUND",
    "message": "No attachment found for this support request",
    "details": null
  }
}
```

### Error response — `403 Forbidden`

```json
{
  "success": false,
  "error": {
    "code": "FORBIDDEN",
    "message": "You do not have permission to access this resource",
    "details": null
  }
}
```
