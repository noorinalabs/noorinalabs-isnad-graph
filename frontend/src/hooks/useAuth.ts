import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { createElement } from 'react'

export type UserRole = 'viewer' | 'editor' | 'moderator' | 'admin'

export interface AuthUser {
  id: string
  email: string
  name: string
  is_admin: boolean
  provider: string
  role: UserRole | null
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
}

const ROLE_HIERARCHY: Record<UserRole, number> = {
  viewer: 0,
  editor: 1,
  moderator: 2,
  admin: 3,
}

const API_BASE = '/api/v1'

const AuthContext = createContext<AuthContextValue | null>(null)

function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
  return match ? match[1] : ''
}

async function refreshAccessToken(): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
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
      fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {})
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

      let res = await fetch(`${API_BASE}/auth/me`, {
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
        res = await fetch(`${API_BASE}/auth/me`, {
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

    // Call logout endpoint (best-effort — clear tokens regardless)
    if (token) {
      try {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
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

  const signOutAll = useCallback(async () => {
    const token = localStorage.getItem('access_token')

    if (token) {
      try {
        await fetch(`${API_BASE}/auth/logout-all`, {
          method: 'POST',
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

  const userRole: UserRole = user?.role ?? 'viewer'

  const hasRole = useCallback(
    (minRole: UserRole): boolean => {
      return ROLE_HIERARCHY[userRole] >= ROLE_HIERARCHY[minRole]
    },
    [userRole],
  )

  const value: AuthContextValue = {
    user,
    loading,
    isAdmin: user?.is_admin ?? false,
    role: userRole,
    hasRole,
    sessionExpired,
    isNewUser,
    logout,
    signOut,
    signOutAll,
    dismissSessionExpired,
    dismissOnboarding,
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
