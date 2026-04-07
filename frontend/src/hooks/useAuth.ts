import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { createElement } from 'react'

export interface AuthUser {
  id: string
  email: string
  name: string
  is_admin: boolean
  provider: string
}

interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  isAdmin: boolean
  sessionExpired: boolean
  logout: () => void
  signOut: () => Promise<void>
  signOutAll: () => Promise<void>
  dismissSessionExpired: () => void
}

const API_BASE = '/api/v1'

const AuthContext = createContext<AuthContextValue | null>(null)

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) return null

  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${refreshToken}`,
      },
    })

    if (!res.ok) return null

    const data = await res.json()
    localStorage.setItem('access_token', data.access_token)
    if (data.refresh_token) {
      localStorage.setItem('refresh_token', data.refresh_token)
    }
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

  const clearTokens = useCallback(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setUser(null)
  }, [])

  const logout = useCallback(() => {
    const token = localStorage.getItem('access_token')
    if (token) {
      fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {})
    }
    clearTokens()
    window.location.href = '/login'
  }, [clearTokens])

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

      // If access token expired, try refreshing
      if (res.status === 401) {
        token = await refreshAccessToken()
        if (!token) {
          // Initial load — no user was shown yet, so redirect normally
          clearTokens()
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
  }, [clearTokens])

  const signOut = useCallback(async () => {
    const token = localStorage.getItem('access_token')

    // Call logout endpoint (best-effort — clear tokens regardless)
    if (token) {
      try {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        })
      } catch {
        // Ignore network errors — we still clear local state
      }
    }

    clearTokens()
    setSessionExpired(false)
    window.location.href = '/login'
  }, [clearTokens])

  const signOutAll = useCallback(async () => {
    const token = localStorage.getItem('access_token')

    if (token) {
      try {
        await fetch(`${API_BASE}/auth/logout-all`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        })
      } catch {
        // Ignore network errors — we still clear local state
      }
    }

    clearTokens()
    setSessionExpired(false)
    window.location.href = '/login'
  }, [clearTokens])

  const dismissSessionExpired = useCallback(() => {
    // User clicks "Sign In" on the re-auth modal — store current URL and redirect to login
    sessionStorage.setItem('oauth_return_url', window.location.pathname + window.location.search)
    clearTokens()
    setSessionExpired(false)
    window.location.href = '/login'
  }, [clearTokens])

  const value: AuthContextValue = {
    user,
    loading,
    isAdmin: user?.is_admin ?? false,
    sessionExpired,
    logout,
    signOut,
    signOutAll,
    dismissSessionExpired,
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
