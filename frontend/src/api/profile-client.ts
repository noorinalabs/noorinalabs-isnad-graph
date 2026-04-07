import { emitSessionExpired } from '../hooks/useAuth'

const API_BASE = '/api/v1/users/me'

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

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
  const res = await fetch(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}`, {
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
