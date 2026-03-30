# Security Headers & CORS Audit Report

**Date:** 2026-03-29
**Auditor:** Yara Hadid, Senior Security Engineer
**Scope:** All HTTP responses from the isnad-graph FastAPI application
**Reference:** OWASP Secure Headers Project, MDN Web Security Guidelines

---

## 1. CORS Configuration

### 1.1 Findings (Before)

| Setting | Value | Severity | Status |
|---------|-------|----------|--------|
| `allow_origins` | `settings.cors_origins` (default `["http://localhost:3000"]`) | OK | No wildcard in production |
| `allow_credentials` | `True` | OK | Required for cookie-based refresh tokens |
| `allow_methods` | `["GET", "POST"]` | Medium | Missing `PATCH` used by admin routes, missing `OPTIONS` for explicit preflight |
| `allow_headers` | `["*"]` | Medium | Wildcard headers weaken CORS; should be explicit |

### 1.2 Remediation Applied

- **`allow_methods`** changed to `["GET", "POST", "PATCH", "OPTIONS"]` to cover admin PATCH endpoints and explicit preflight handling.
- **`allow_headers`** changed to `["Authorization", "Content-Type", "Accept", "X-Request-ID"]` -- explicit allowlist per OWASP best practice. The wildcard `*` was removed because it can allow unexpected custom headers to pass through CORS preflight.

### 1.3 Verification

- Preflight OPTIONS to allowed origin returns correct `Access-Control-Allow-Origin` (not `*`).
- Preflight from disallowed origin receives no `Access-Control-Allow-Origin` header.
- `Access-Control-Allow-Credentials: true` is present.
- PATCH method is allowed in preflight response.
- Authorization header is explicitly allowed.

---

## 2. Security Response Headers

### 2.1 Audit Matrix

| Header | Before | After | Severity | Notes |
|--------|--------|-------|----------|-------|
| `X-Content-Type-Options` | `nosniff` | `nosniff` | -- | Already correct |
| `X-Frame-Options` | `DENY` (configurable) | `DENY` (configurable) | -- | Already correct |
| `X-XSS-Protection` | `1; mode=block` | `0` | **High** | Legacy XSS Auditor can introduce cross-site leak vulnerabilities. OWASP recommends `0`; CSP provides protection. |
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains` | `max-age=63072000; includeSubDomains; preload` | Medium | Added `preload` directive for HSTS preload list eligibility |
| `Content-Security-Policy` | `default-src 'self'` | `default-src 'self'; frame-ancestors 'none'` | Medium | Added `frame-ancestors 'none'` for defense-in-depth with X-Frame-Options |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | `strict-origin-when-cross-origin` | -- | Already correct |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | `camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()` | Low | Extended to disable Payment Request API, WebUSB, and FLoC |
| `Cross-Origin-Opener-Policy` | **Missing** | `same-origin` | **High** | Prevents cross-origin window references (Spectre mitigation) |
| `Cross-Origin-Resource-Policy` | **Missing** | `same-origin` | **High** | Prevents cross-origin reads of resources (Spectre mitigation) |

### 2.2 Headers Not Added (Intentional)

| Header | Reason |
|--------|--------|
| `Cross-Origin-Embedder-Policy` | Setting to `require-corp` would break legitimate cross-origin API usage from the React frontend. Not appropriate for an API server. |
| `Expect-CT` | Deprecated; Certificate Transparency is now enforced by browsers by default. |

---

## 3. Configuration

All new headers are configurable via environment variables with the `SECURITY_` prefix:

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `SECURITY_HSTS_PRELOAD` | `true` | Include `preload` directive in HSTS |
| `SECURITY_CROSS_ORIGIN_OPENER_POLICY` | `same-origin` | COOP header value |
| `SECURITY_CROSS_ORIGIN_RESOURCE_POLICY` | `same-origin` | CORP header value |
| `SECURITY_PERMISSIONS_POLICY` | (see above) | Full Permissions-Policy value |
| `SECURITY_CONTENT_SECURITY_POLICY` | `default-src 'self'; frame-ancestors 'none'` | CSP directive |

---

## 4. Test Coverage

New and updated tests in `tests/test_auth/test_security.py`:

- `TestSecurityHeaders`: Updated tests for X-XSS-Protection (`0`), HSTS preload, CSP frame-ancestors, COOP, CORP, extended Permissions-Policy
- `TestCORSConfiguration`: 6 new tests covering allowed/disallowed origins, wildcard rejection, PATCH preflight, explicit header allowlist, credentials mode

All 41 security tests pass.

---

## 5. Risk Summary

| Severity | Count | Status |
|----------|-------|--------|
| Critical | 0 | -- |
| High | 3 | Fixed (X-XSS-Protection, COOP, CORP) |
| Medium | 3 | Fixed (CORS methods, CORS headers, HSTS preload, CSP frame-ancestors) |
| Low | 1 | Fixed (Permissions-Policy extended) |
