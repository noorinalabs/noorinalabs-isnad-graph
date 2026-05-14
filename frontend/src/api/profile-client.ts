import { emitSessionExpired } from '../hooks/useAuth'
import { getAuthHeaders } from './auth-headers'

// Absolute URLs targeting the user-service vhost (`users.{base}`). See
// useAuth.ts for the full BASE-constant set; kept duplicated here to avoid
// a barrel-export refactor inside this PR.
const USER_SERVICE_ORIGIN = import.meta.env.VITE_USER_SERVICE_ORIGIN ?? ''
const USERS_BASE = `${USER_SERVICE_ORIGIN}/api/v1/users`
const SESSIONS_BASE = `${USER_SERVICE_ORIGIN}/api/v1/sessions`

async function fetchProfileJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { ...getAuthHeaders(), ...init?.headers },
  })
  if (res.status === 401) {
    emitSessionExpired()
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

// Mirrors user-service `UserRead` (src/app/schemas/user.py). `display_name`
// can legitimately be null — consumers must null-defense reads.
export interface UserProfile {
  id: string
  email: string
  display_name: string | null
  email_verified: boolean
  avatar_url: string | null
  locale: string | null
  is_active: boolean
  created_at: string
  roles: string[]
}

// Mirrors user-service `SessionResponse` (src/app/schemas/session.py).
export interface SessionInfo {
  id: string
  ip_address: string | null
  user_agent: string | null
  created_at: string
  last_active: string
  expires_at: string
  is_current: boolean
}

// Mirrors user-service `SessionListResponse`.
interface SessionListResponse {
  sessions: SessionInfo[]
  count: number
}

export async function fetchProfile(): Promise<UserProfile> {
  return fetchProfileJson(`${USERS_BASE}/me`)
}

// user-service `UserUpdate` accepts display_name, avatar_url, locale.
export async function updateProfile(body: {
  display_name?: string
  avatar_url?: string
  locale?: string
}): Promise<UserProfile> {
  return fetchProfileJson(`${USERS_BASE}/me`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function fetchSessions(): Promise<SessionInfo[]> {
  const data = await fetchProfileJson<SessionListResponse>(SESSIONS_BASE)
  return data.sessions
}

export async function revokeSession(sessionId: string): Promise<void> {
  const res = await fetch(`${SESSIONS_BASE}/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  })
  if (res.status === 401) {
    emitSessionExpired()
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }
}
