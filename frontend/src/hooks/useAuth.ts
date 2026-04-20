import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { createElement } from 'react'

export type UserRole = 'viewer' | 'editor' | 'moderator' | 'admin'

/**
 * Shape of `/api/v1/users/me` (user-service UserRead schema).
 *
 * `display_name` is the canonical name field from the API. It can legitimately
 * be null — consumers MUST null-defense every read (prefer `user.display_name ?? user.email`).
 *
 * `roles` is a list of role *names* (strings), matching user-service
 * `UserRead.roles: list[str]` in `src/app/schemas/user.py`. Serialized from
 * `[ur.role.name for ur in u.user_roles]` in `src/app/routers/users.py`. Use
 * `deriveHighestRole(roles)` to map to the `UserRole` union.
 *
 * `provider` is NOT part of the user-service `/users/me` payload today; it is
 * kept here as optional because the OAuth callback path on the isnad-graph
 * side may populate it from JWT claims before the user is loaded. Readers
 * (e.g. `UserMenu`) already null-guard it, so it gracefully degrades.
 */
export interface AuthUser {
  id: string
  email: string
  display_name: string | null
  avatar_url: string | null
  email_verified: boolean
  is_active: boolean
  locale: string | null
  created_at: string
  roles: string[]
  // Optional — not returned by /users/me today; may be populated from JWT
  // claims during OAuth callback. See UserMenu.tsx for the sole reader.
  provider?: string
}

interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  isAdmin: boolean
  role: UserRole
  hasRole: (minRole: UserRole) => boolean
  sessionExpired: boolean
  isNewUser: boolean
  logout: () => void
  signOut: () => Promise<void>
  signOutAll: () => Promise<void>
  dismissSessionExpired: () => void
  dismissOnboarding: () => void
  refreshUser: () => Promise<void>
}

const ROLE_HIERARCHY: Record<UserRole, number> = {
  viewer: 0,
  editor: 1,
  moderator: 2,
  admin: 3,
}

/**
 * Map a list of role names (as returned by user-service) to the highest
 * matching `UserRole` in the frontend hierarchy. Unknown role names
 * (e.g. user-service DB roles like `researcher`, `reader`, `trial` that
 * aren't yet represented in the frontend union) are ignored — callers
 * default to `viewer` for fully-unknown sets.
 *
 * NOTE: if `UserRole` is extended to cover additional backend roles, add
 * them to `ROLE_HIERARCHY` above and they will automatically participate
 * in derivation here (we iterate the hierarchy highest-first).
 */
export function deriveHighestRole(roleNames: string[]): UserRole {
  // Iterate ROLE_HIERARCHY from highest rank to lowest; return first match.
  const ordered = (Object.keys(ROLE_HIERARCHY) as UserRole[]).sort(
    (a, b) => ROLE_HIERARCHY[b] - ROLE_HIERARCHY[a],
  )
  for (const tier of ordered) {
    if (roleNames.includes(tier)) return tier
  }
  return 'viewer'
}

const AUTH_BASE = '/auth'
const USER_BASE = '/api/v1/users'
const SESSIONS_BASE = '/api/v1/sessions'

const AuthContext = createContext<AuthContextValue | null>(null)

function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
  return match?.[1] ?? ''
}

async function refreshAccessToken(): Promise<string | null> {
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
    return null
  }
}

/**
 * Event emitted when an API call receives a 401 mid-session.
 * The AuthProvider listens for this to show the re-auth modal.
 */
export const SESSION_EXPIRED_EVENT = 'auth:session-expired'

export function emitSessionExpired() {
  window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT))
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [sessionExpired, setSessionExpired] = useState(false)
  const [isNewUser, setIsNewUser] = useState(false)

  const clearAuth = useCallback(() => {
    localStorage.removeItem('access_token')
    setUser(null)
    setIsNewUser(false)
  }, [])

  // Check for new-user flag set by AuthCallbackPage
  useEffect(() => {
    const flag = sessionStorage.getItem('is_new_user')
    if (flag === '1') {
      setIsNewUser(true)
      sessionStorage.removeItem('is_new_user')
    }
  }, [])

  const logout = useCallback(() => {
    const token = localStorage.getItem('access_token')
    if (token) {
      // Revoke only the current session (best-effort)
      const headers = { Authorization: `Bearer ${token}` }
      fetch(`${SESSIONS_BASE}`, { headers, credentials: 'include' })
        .then((res) => (res.ok ? res.json() : Promise.reject(res)))
        .then((data: { sessions: Array<{ id: string; is_current: boolean }> }) => {
          const current = data.sessions.find((s) => s.is_current)
          if (current) {
            return fetch(`${SESSIONS_BASE}/${current.id}`, {
              method: 'DELETE',
              credentials: 'include',
              headers,
            })
          }
        })
        .catch(() => {})
    }
    clearAuth()
    window.location.href = '/login'
  }, [clearAuth])

  // Listen for session-expired events from API clients
  useEffect(() => {
    function handleSessionExpired() {
      // Only show re-auth modal if user was previously authenticated
      if (user) {
        setSessionExpired(true)
      }
    }
    window.addEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired)
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired)
  }, [user])

  useEffect(() => {
    async function loadUser() {
      let token = localStorage.getItem('access_token')
      if (!token) {
        setLoading(false)
        return
      }

      let res = await fetch(`${USER_BASE}/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })

      // If access token expired, try refreshing via httpOnly cookie
      if (res.status === 401) {
        token = await refreshAccessToken()
        if (!token) {
          // Initial load — no user was shown yet, so redirect normally
          clearAuth()
          setLoading(false)
          return
        }
        res = await fetch(`${USER_BASE}/me`, {
          headers: { Authorization: `Bearer ${token}` },
        })
      }

      if (res.ok) {
        const data: AuthUser = await res.json()
        setUser(data)
      } else {
        setUser(null)
      }
      setLoading(false)
    }

    loadUser()
  }, [clearAuth])

  const signOut = useCallback(async () => {
    const token = localStorage.getItem('access_token')

    // Revoke only the current session (best-effort — clear tokens regardless)
    if (token) {
      try {
        const headers = { Authorization: `Bearer ${token}` }
        const res = await fetch(`${SESSIONS_BASE}`, { headers, credentials: 'include' })
        if (res.ok) {
          const data: { sessions: Array<{ id: string; is_current: boolean }> } = await res.json()
          const current = data.sessions.find((s) => s.is_current)
          if (current) {
            await fetch(`${SESSIONS_BASE}/${current.id}`, {
              method: 'DELETE',
              credentials: 'include',
              headers,
            })
          }
        }
      } catch {
        // Ignore network errors — we still clear local state
      }
    }

    clearAuth()
    setSessionExpired(false)
    window.location.href = '/login'
  }, [clearAuth])

  const signOutAll = useCallback(async () => {
    const token = localStorage.getItem('access_token')

    // Revoke ALL sessions for this user
    if (token) {
      try {
        await fetch(`${SESSIONS_BASE}`, {
          method: 'DELETE',
          credentials: 'include',
          headers: { Authorization: `Bearer ${token}` },
        })
      } catch {
        // Ignore network errors — we still clear local state
      }
    }

    clearAuth()
    setSessionExpired(false)
    window.location.href = '/login'
  }, [clearAuth])

  const dismissSessionExpired = useCallback(() => {
    // User clicks "Sign In" on the re-auth modal — store current URL and redirect to login
    sessionStorage.setItem('oauth_return_url', window.location.pathname + window.location.search)
    clearAuth()
    setSessionExpired(false)
    window.location.href = '/login'
  }, [clearAuth])

  const dismissOnboarding = useCallback(() => {
    setIsNewUser(false)
  }, [])

  const refreshUser = useCallback(async () => {
    const token = localStorage.getItem('access_token')
    if (!token) return
    try {
      const res = await fetch(`${USER_BASE}/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const data: AuthUser = await res.json()
        setUser(data)
      }
    } catch {
      // Silently ignore — this is a background refresh
    }
  }, [])

  const userRole: UserRole = deriveHighestRole(user?.roles ?? [])
  const isAdmin = (user?.roles ?? []).includes('admin')

  const hasRole = useCallback(
    (minRole: UserRole): boolean => {
      return ROLE_HIERARCHY[userRole] >= ROLE_HIERARCHY[minRole]
    },
    [userRole],
  )

  const value: AuthContextValue = {
    user,
    loading,
    isAdmin,
    role: userRole,
    hasRole,
    sessionExpired,
    isNewUser,
    logout,
    signOut,
    signOutAll,
    dismissSessionExpired,
    dismissOnboarding,
    refreshUser,
  }

  return createElement(AuthContext.Provider, { value }, children)
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (ctx === null) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return ctx
}
