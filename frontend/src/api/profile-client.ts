import { emitSessionExpired } from '../hooks/useAuth'
import { getAuthHeaders } from './auth-headers'
import { refreshAccessToken } from './token-refresh'
import { apiError } from './api-error'

// Absolute URLs targeting the user-service vhost (`users.{base}`). See
// useAuth.ts for the full BASE-constant set and the runtime-vs-build-time
// resolution rationale; kept duplicated here to avoid a barrel-export refactor
// inside this PR.
const USER_SERVICE_ORIGIN =
  (typeof window !== 'undefined' && window.RUNTIME_CONFIG?.USER_SERVICE_ORIGIN) ||
  import.meta.env.VITE_USER_SERVICE_ORIGIN ||
  ''
// `/api/v1/users/me` covers the user record (PATCH) and its preferences blob
// (`/profile`). Sessions are a sibling collection at `/api/v1/sessions` — NOT
// under `/users/me` — matching the user-service routers (us#165 / sessions US#7).
const USER_BASE = `${USER_SERVICE_ORIGIN}/api/v1/users/me`
const SESSIONS_BASE = `${USER_SERVICE_ORIGIN}/api/v1/sessions`

// Issue an authenticated request; on a 401 attempt ONE shared token refresh
// (POST /auth/token/refresh via the httpOnly refresh cookie) and retry the
// request once before the caller surfaces session-expired. Only a genuinely
// expired/revoked refresh cookie (a failed refresh) leaves the response at 401
// — a mid-session access-token expiry no longer logs the user out of their
// profile. getAuthHeaders() re-reads the freshly persisted token on the retry.
// Mirrors client.ts `fetchJson` (#1016); shared by every profile 401 path so a
// 401 from one client no longer diverges from the others (#1021).
async function fetchWithRefresh(url: string, init?: RequestInit): Promise<Response> {
  const send = () =>
    fetch(url, { ...init, headers: { ...getAuthHeaders(), ...init?.headers } })
  let res = await send()
  if (res.status === 401) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      res = await send()
    }
  }
  return res
}

async function fetchProfileJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetchWithRefresh(url, init)
  if (res.status === 401) {
    emitSessionExpired()
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    throw apiError(res)
  }
  return res.json() as Promise<T>
}

/**
 * A user's UI/UX preferences (the JSONB blob behind `/users/me/profile`).
 *
 * The user-service type-checks only the two well-known keys — `theme` and
 * `language` — and round-trips any other key untouched (`extra="allow"`, 8 KB
 * cap). The index signature models that pass-through: a read-modify-write of the
 * whole object must preserve keys this client does not know about.
 */
export interface UserPreferences {
  theme?: 'light' | 'dark' | 'system'
  language?: string
  default_search_mode?: string
  results_per_page?: number
  [key: string]: unknown
}

export interface ProfileRead {
  user_id: string
  preferences: UserPreferences
}

export interface SessionInfo {
  id: string
  ip_address: string | null
  user_agent: string | null
  created_at: string
  last_active: string
  expires_at: string
  is_current: boolean
}

interface SessionListResponse {
  sessions: SessionInfo[]
  count: number
}

export async function fetchProfile(): Promise<ProfileRead> {
  return fetchProfileJson(`${USER_BASE}/profile`)
}

/**
 * Replace the preferences blob wholesale. The endpoint is PUT with REPLACE
 * semantics (us#165) — there is no server-side merge — so callers MUST pass the
 * full object (read-modify-write) or unrelated keys are dropped.
 */
export async function replacePreferences(preferences: UserPreferences): Promise<ProfileRead> {
  return fetchProfileJson(`${USER_BASE}/profile`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ preferences }),
  })
}

/**
 * Update the display name. This lives on the user record, not the preferences
 * blob, so it is a PATCH to `/users/me` (UserUpdate) — distinct from the
 * preferences PUT above.
 */
export async function updateDisplayName(displayName: string): Promise<void> {
  await fetchProfileJson(USER_BASE, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ display_name: displayName }),
  })
}

export async function fetchSessions(): Promise<SessionInfo[]> {
  // The list endpoint wraps the rows in `{ sessions, count }`; callers want the rows.
  const data = await fetchProfileJson<SessionListResponse>(SESSIONS_BASE)
  return data.sessions
}

export async function revokeSession(sessionId: string): Promise<void> {
  const res = await fetchWithRefresh(`${SESSIONS_BASE}/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
  })
  if (res.status === 401) {
    emitSessionExpired()
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    throw apiError(res)
  }
}
