// Mint a short-lived parent-domain SSO cookie so an admin can cross from the app
// (isnad-graph.{base}) into the Grafana/observability subdomain without hitting
// Grafana's own login wall. This is the frontend third of the admin-gated-Grafana
// SSO feature (noorinalabs-deploy#458 / user-service#171).
//
// Flow: POST /auth/sso-cookie (authenticated with the current app access token),
// the user-service responds with a `Set-Cookie` for `nl_sso`
// (Domain=noorinalabs.com, HttpOnly, Secure, SameSite=Lax, Max-Age=300). Because
// it is HttpOnly the frontend can never READ it — the only job here is to TRIGGER
// the mint and let the browser store it. The caller then does a top-level
// `window.location` navigation to the observability URL; SameSite=Lax lets the
// browser carry the parent-domain cookie on that cross-subdomain top-level nav,
// and forward_auth on the Grafana vhost validates it.
//
// `credentials: 'include'` is MANDATORY: without it the browser discards the
// `Set-Cookie` from the fetch response and the subsequent navigation carries no
// credential.

import { getAuthHeaders } from './auth-headers'
import { refreshAccessToken } from './token-refresh'
import { apiError } from './api-error'

// Absolute URL targeting the user-service vhost (`users.{base}`). Resolved at
// runtime from `window.RUNTIME_CONFIG` (injected by the container entrypoint via
// /runtime-config.js), falling back to the build-time `VITE_USER_SERVICE_ORIGIN`
// for local `npm run dev`, then '' (same-origin). Mirrors token-refresh.ts /
// useAuth.ts (isnad-graph#932) — kept duplicated to avoid a barrel-export
// refactor inside this PR.
const USER_SERVICE_ORIGIN =
  (typeof window !== 'undefined' && window.RUNTIME_CONFIG?.USER_SERVICE_ORIGIN) ||
  import.meta.env.VITE_USER_SERVICE_ORIGIN ||
  ''
const AUTH_BASE = `${USER_SERVICE_ORIGIN}/auth`

export interface SsoCookieResult {
  status: string
  cookie_name: string
  expires_in: number
}

/**
 * Mint the `nl_sso` parent-domain cookie (POST /auth/sso-cookie). Mirrors the
 * shared #1016/#1021 recovery: on a 401 attempt ONE token refresh (via the
 * httpOnly refresh cookie) and retry once before failing. Throws an
 * {@link ApiError} on a non-OK response (or a network failure) so the caller can
 * surface an inline error and skip the navigation. The cookie itself is HttpOnly
 * and never visible to JS; the resolved value is only the JSON acknowledgement.
 */
export async function mintSsoCookie(): Promise<SsoCookieResult> {
  const send = () =>
    fetch(`${AUTH_BASE}/sso-cookie`, {
      method: 'POST',
      // Required so the browser stores the parent-domain Set-Cookie response.
      credentials: 'include',
      headers: { ...getAuthHeaders() },
    })

  let res = await send()
  if (res.status === 401) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      res = await send()
    }
  }
  if (!res.ok) {
    throw apiError(res)
  }
  return res.json() as Promise<SsoCookieResult>
}
