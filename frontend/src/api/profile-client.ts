import { emitSessionExpired } from '../hooks/useAuth'
import { getAuthHeaders } from './auth-headers'
import { refreshAccessToken } from './token-refresh'
import { apiError } from './api-error'

// Absolute URL targeting the user-service vhost (`users.{base}`). See
// useAuth.ts for the full BASE-constant set and the runtime-vs-build-time
// resolution rationale; kept duplicated here to avoid a barrel-export refactor
// inside this PR.
const USER_SERVICE_ORIGIN =
  (typeof window !== 'undefined' && window.RUNTIME_CONFIG?.USER_SERVICE_ORIGIN) ||
  import.meta.env.VITE_USER_SERVICE_ORIGIN ||
  ''
const API_BASE = `${USER_SERVICE_ORIGIN}/api/v1/users/me`

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

export interface UserPreferences {
  default_search_mode: string
  results_per_page: number
  language_preference: string
  theme_preference: string
}

export interface UserProfile {
  id: string
  email: string
  name: string
  provider: string
  role: string | null
  is_admin: boolean
  created_at: string
  preferences: UserPreferences
}

export interface SessionInfo {
  id: string
  created_at: string
  last_active: string
  ip_address: string | null
  user_agent: string | null
  is_current: boolean
}

export async function fetchProfile(): Promise<UserProfile> {
  return fetchProfileJson(`${API_BASE}/profile`)
}

export async function updateProfile(body: {
  display_name?: string
  preferences?: UserPreferences
}): Promise<UserProfile> {
  return fetchProfileJson(`${API_BASE}/profile`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function fetchSessions(): Promise<SessionInfo[]> {
  return fetchProfileJson(`${API_BASE}/sessions`)
}

export async function revokeSession(sessionId: string): Promise<void> {
  const res = await fetchWithRefresh(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}`, {
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
