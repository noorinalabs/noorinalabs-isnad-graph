# API Developer Guide

Internal reference for consuming the isnad-graph API.

## Base URL

```
http://localhost:8000          # local dev
https://isnad-graph.noorinalabs.com/api  # production
```

All versioned endpoints are prefixed with `/api/v1`.

## Interactive Docs

- **Swagger UI** — `GET /docs`
- **ReDoc** — `GET /redoc`
- **OpenAPI JSON** — `GET /openapi.json`

## Authentication Flow

The API uses OAuth 2.0 with PKCE for login and JWT bearer tokens for session
management.  Supported providers: Google, Apple, Facebook, GitHub.

### 1. Initiate Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login/google
```

Response:

```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
}
```

Redirect the user's browser to `authorization_url`.

### 2. Handle Callback

After consent, the provider redirects to the callback URL with `code` and
`state` query parameters.  The API exchanges the code for tokens:

```
GET /api/v1/auth/callback/google?code=<code>&state=<state>
```

Response:

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### 3. Authenticated Requests

Include the access token in the `Authorization` header:

```bash
curl -H "Authorization: Bearer eyJ..." \
     http://localhost:8000/api/v1/narrators?page=1&limit=20
```

### 4. Refresh Tokens

Before the access token expires, rotate it:

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
     -H "Content-Type: application/json" \
     -d '{"refresh_token": "eyJ..."}'
```

The old refresh token is revoked and a new pair is returned.

### 5. Logout

```bash
curl -X POST http://localhost:8000/api/v1/auth/logout \
     -H "Authorization: Bearer eyJ..."
```

Returns `204 No Content`.

### 6. Current User

```bash
curl -H "Authorization: Bearer eyJ..." \
     http://localhost:8000/api/v1/auth/me
```

## Endpoint Overview

| Group | Endpoints | Auth Required |
|-------|-----------|---------------|
| Health | `GET /health` | No |
| Auth | `POST /api/v1/auth/login/{provider}`, `GET /api/v1/auth/callback/{provider}`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me` | Varies |
| Narrators | `GET /api/v1/narrators`, `GET /api/v1/narrators/{id}`, `GET /api/v1/narrators/{id}/chains`, `GET /api/v1/narrators/{id}/network` | Yes |
| Hadiths | `GET /api/v1/hadiths`, `GET /api/v1/hadiths/{id}`, `GET /api/v1/hadiths/{id}/chain` | Yes |
| Collections | `GET /api/v1/collections`, `GET /api/v1/collections/{id}` | Yes |
| Graph | `GET /api/v1/graph/shortest-path`, `GET /api/v1/graph/subgraph` | Yes |
| Search | `GET /api/v1/search` | Yes |
| Parallels | `GET /api/v1/parallels/{hadith_id}`, `GET /api/v1/parallels` | Yes |
| Timeline | `GET /api/v1/timeline`, `GET /api/v1/timeline/range` | Yes |
| 2FA | `POST /api/v1/2fa/enroll`, `POST /api/v1/2fa/verify` | Yes |

## Rate Limiting

- **120 requests/minute** per client IP (sliding window).
- Exceeding the limit returns `429 Too Many Requests` with `Retry-After: 60`.

## Request Size Limit

Maximum request body: **1 MB** (1,048,576 bytes). Larger payloads receive
`413 Request Entity Too Large`.

## Error Response Format

All errors follow the standard FastAPI format:

```json
{
  "detail": "Human-readable error message"
}
```

| Status | Meaning |
|--------|---------|
| 400 | Bad request / invalid parameters |
| 401 | Missing, invalid, or expired token |
| 404 | Resource not found |
| 413 | Request body too large |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

## Security Headers

All responses include OWASP-recommended headers:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security: max-age=63072000; includeSubDomains`
- `Content-Security-Policy: default-src 'self'`
- `Referrer-Policy: strict-origin-when-cross-origin`
