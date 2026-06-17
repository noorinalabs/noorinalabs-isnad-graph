import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { createElement } from 'react'
import type { components } from '../types/user-service'
import { refreshAccessToken } from '../api/token-refresh'
import { readJsonResponse } from '../lib/authJson'

export type UserRole = 'trial' | 'reader' | 'researcher' | 'admin'

/**
 * Shape of `/api/v1/users/me` — the base type is generated from the committed
 * user-service OpenAPI snapshot (`frontend/docs/openapi-snapshot.json` →
 * `frontend/src/types/user-service.d.ts` via `npm run gen:types`). Drift between
 * the snapshot and the generated `.d.ts` is enforced at PR-time by the
 * `frontend-typegen-drift` CI job.
 *
 * `display_name` is the canonical name field from the API. It can legitimately
 * be null — consumers MUST null-defense every read (prefer `user.display_name ?? user.email`).
 *
 * `roles` is a list of role *names* (strings). Use `deriveHighestRole(roles)`
 * to map to the `UserRole` union.
 *
 * `provider` is NOT part of the user-service `/users/me` payload today; it is
 * kept here as optional (added via the interface extension below) because the
 * OAuth callback path on the isnad-graph side may populate it from JWT claims
 * before the user is loaded. Readers (e.g. `UserMenu`) already null-guard it,
 * so it gracefully degrades.
 */
export type AuthUser = components['schemas']['UserRead'] & {
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

// Mirrors the user-service canonical hierarchy (ontology/repos/user-service.yaml:69
// → { admin: 40, researcher: 30, reader: 20, trial: 10 }), rescaled to 0-indexed
// ranks. Order matters for `deriveHighestRole` highest-first iteration.
const ROLE_HIERARCHY: Record<UserRole, number> = {
  trial: 0,
  reader: 1,
  researcher: 2,
  admin: 3,
}

/**
 * Map a list of role names (as returned by user-service `UserRead.roles`) to
 * the highest matching `UserRole`. The frontend union is reconciled with the
 * backend vocabulary as of #876 — any string outside `trial|reader|researcher|admin`
 * is unknown and ignored; if no known role matches, callers default to `trial`
 * (the lowest tier — least permissive).
 */
export function deriveHighestRole(roleNames: string[]): UserRole {
  const ordered = (Object.keys(ROLE_HIERARCHY) as UserRole[]).sort(
    (a, b) => ROLE_HIERARCHY[b] - ROLE_HIERARCHY[a],
  )
  for (const tier of ordered) {
    if (roleNames.includes(tier)) return tier
  }
  return 'trial'
}

// Absolute URLs targeting the user-service vhost (`users.{base}`). Resolved at
// runtime from `window.RUNTIME_CONFIG` (injected by the container entrypoint via
// /runtime-config.js) so a single image digest targets env-specific origins —
// Vite can bake only one VITE_* value into the bundle (Contract v6, #815).
// Falls back to the build-time `VITE_USER_SERVICE_ORIGIN` for local `npm run dev`
// (no entrypoint), then to '' (same-origin). See isnad-graph#932 / deploy#245 step 5.
//
// The `/auth/token/refresh` exchange itself now lives in `api/token-refresh.ts`
// (single source of truth, shared with the data clients per #1016) — hence no
// AUTH_BASE / getCsrfToken here anymore.
const USER_SERVICE_ORIGIN =
  (typeof window !== 'undefined' && window.RUNTIME_CONFIG?.USER_SERVICE_ORIGIN) ||
  import.meta.env.VITE_USER_SERVICE_ORIGIN ||
  ''
const USER_BASE = `${USER_SERVICE_ORIGIN}/api/v1/users`
const SESSIONS_BASE = `${USER_SERVICE_ORIGIN}/api/v1/sessions`

const AuthContext = createContext<AuthContextValue | null>(null)

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
        .then((res) =>
          res.ok
            ? readJsonResponse<{ sessions: Array<{ id: string; is_current: boolean }> }>(res)
            : Promise.reject(res),
        )
        .then((data) => {
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
        try {
          const data = await readJsonResponse<AuthUser>(res)
          setUser(data)
        } catch {
          // Non-JSON 200 (e.g. a misrouted origin serving index.html — the
          // deploy#420 class). Treat as unauthenticated rather than letting an
          // unhandled parse error leave the app stuck on the loading spinner.
          setUser(null)
        }
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
          const data =
            await readJsonResponse<{ sessions: Array<{ id: string; is_current: boolean }> }>(res)
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
        const data = await readJsonResponse<AuthUser>(res)
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
