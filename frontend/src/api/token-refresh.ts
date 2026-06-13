// Shared access-token refresh machinery (#1016).
//
// The user-service issues short-lived access tokens (held in localStorage) plus
// a long-lived refresh token in an httpOnly, SameSite cookie. When an access
// token expires mid-session every API client gets a 401; the cure is a single
// `POST /auth/token/refresh` (the browser sends the refresh cookie), which mints
// a fresh access token. Previously only `useAuth.loadUser` knew how to do this,
// so the data clients force-logged-out on any 401. This module is the single
// source of truth for that exchange so every client recovers identically and the
// endpoint logic never diverges.

// Absolute URL targeting the user-service vhost (`users.{base}`). Resolved at
// runtime from `window.RUNTIME_CONFIG` (injected by the container entrypoint via
// /runtime-config.js) so a single image digest targets env-specific origins,
// falling back to the build-time `VITE_USER_SERVICE_ORIGIN` for local
// `npm run dev`, then '' (same-origin). Mirrors useAuth.ts (isnad-graph#932).
const USER_SERVICE_ORIGIN =
  (typeof window !== 'undefined' && window.RUNTIME_CONFIG?.USER_SERVICE_ORIGIN) ||
  import.meta.env.VITE_USER_SERVICE_ORIGIN ||
  ''
const AUTH_BASE = `${USER_SERVICE_ORIGIN}/auth`

// Double-submit CSRF: the refresh cookie pairs with a readable `csrf_token`
// cookie echoed back in the `X-CSRF-Token` header. Absent → empty string (the
// server rejects, refresh fails closed).
function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
  return match?.[1] ?? ''
}

// Single-flight guard. Concurrent 401s (e.g. a page firing several data calls
// at once) MUST share ONE in-flight refresh rather than each POSTing its own:
// the refresh cookie rotates on use, so parallel refreshes would race and
// invalidate each other, defeating the recovery they're meant to provide. The
// promise is cached for the duration of the request and cleared once it settles
// so the next genuine expiry triggers a fresh exchange.
let inFlight: Promise<string | null> | null = null

async function doRefresh(): Promise<string | null> {
  try {
    const res = await fetch(`${AUTH_BASE}/token/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': getCsrfToken(),
      },
    })

    if (!res.ok) return null

    const data = await res.json()
    localStorage.setItem('access_token', data.access_token)
    return data.access_token as string
  } catch {
    // Network failure / non-JSON body — treat as a failed refresh (caller logs out).
    return null
  }
}

/**
 * Exchange the httpOnly refresh cookie for a fresh access token, persisting it
 * to localStorage on success. Returns the new token, or `null` if the refresh
 * token is genuinely expired/revoked (or the request failed) — in which case
 * the caller should surface session-expired.
 *
 * Single-flight: concurrent callers share one in-flight request.
 */
export function refreshAccessToken(): Promise<string | null> {
  if (!inFlight) {
    inFlight = doRefresh().finally(() => {
      inFlight = null
    })
  }
  return inFlight
}
