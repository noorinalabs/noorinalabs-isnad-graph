import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  type ReactNode,
} from 'react'
import { createElement } from 'react'
import { API_BASE } from '../config'

interface AuthUser {
  id: string
  email: string
  name: string
  is_admin: boolean
}

interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  isAdmin: boolean
  isAuthenticated: boolean
  logout: () => Promise<void>
  refreshAuthState: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

/** Threshold in seconds — refresh proactively when token expires within this window. */
const PROACTIVE_REFRESH_THRESHOLD_S = 60
/** How often to check the expiry cookie (ms). */
const PROACTIVE_CHECK_INTERVAL_MS = 15_000

/** Read a cookie value by name. Returns null if not found. */
function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'))
  return match && match[1] !== undefined ? decodeURIComponent(match[1]) : null
}

/** BroadcastChannel name for cross-tab auth state sync. */
const AUTH_CHANNEL_NAME = 'isnad-auth-sync'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const proactiveTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchAuthState = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, { credentials: 'include' })
      if (!res.ok) throw new Error('Unauthorized')
      const data: AuthUser = await res.json()
      setUser(data)
    } catch {
      setUser(null)
    }
  }, [])

  const refreshAuthState = useCallback(async () => {
    await fetchAuthState()
  }, [fetchAuthState])

  // Expose refreshAuthState globally so client.ts interceptor can call it
  useEffect(() => {
    const w = window as unknown as Record<string, unknown>
    w.__refreshAuthState = refreshAuthState
    return () => {
      delete w.__refreshAuthState
    }
  }, [refreshAuthState])

  // Initial auth state check
  useEffect(() => {
    fetchAuthState().finally(() => setLoading(false))
  }, [fetchAuthState])

  // Proactive token refresh: check the token_expires_at cookie periodically
  useEffect(() => {
    async function checkAndRefresh() {
      const expiresAtStr = getCookie('token_expires_at')
      if (!expiresAtStr) return
      const expiresAt = parseInt(expiresAtStr, 10)
      if (isNaN(expiresAt)) return
      const nowS = Math.floor(Date.now() / 1000)
      if (expiresAt - nowS <= PROACTIVE_REFRESH_THRESHOLD_S) {
        try {
          const res = await fetch(`${API_BASE}/auth/refresh`, {
            method: 'POST',
            credentials: 'include',
          })
          if (res.ok) {
            await refreshAuthState()
            try {
              const bc = new BroadcastChannel(AUTH_CHANNEL_NAME)
              bc.postMessage({ type: 'token-refreshed' })
              bc.close()
            } catch {
              // BroadcastChannel not supported
            }
          }
        } catch {
          // Refresh failed — will be caught by 401 interceptor on next request
        }
      }
    }

    proactiveTimerRef.current = setInterval(checkAndRefresh, PROACTIVE_CHECK_INTERVAL_MS)
    checkAndRefresh()
    return () => {
      if (proactiveTimerRef.current) clearInterval(proactiveTimerRef.current)
    }
  }, [refreshAuthState])

  // Cross-tab sync via BroadcastChannel
  useEffect(() => {
    let bc: BroadcastChannel | null = null
    try {
      bc = new BroadcastChannel(AUTH_CHANNEL_NAME)
      bc.onmessage = (event: MessageEvent) => {
        const msg = event.data as { type: string }
        if (msg.type === 'token-refreshed') {
          refreshAuthState()
        } else if (msg.type === 'logged-out') {
          setUser(null)
          window.location.href = '/login'
        }
      }
    } catch {
      // BroadcastChannel not supported — cross-tab sync unavailable
    }
    return () => {
      if (bc) bc.close()
    }
  }, [refreshAuthState])

  const logout = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      })
    } catch {
      // Clear local state even if the server call fails
    }
    setUser(null)
    try {
      const bc = new BroadcastChannel(AUTH_CHANNEL_NAME)
      bc.postMessage({ type: 'logged-out' })
      bc.close()
    } catch {
      // BroadcastChannel not supported
    }
    window.location.href = '/login'
  }, [])

  const value: AuthContextValue = {
    user,
    loading,
    isAdmin: user?.is_admin ?? false,
    isAuthenticated: user !== null,
    logout,
    refreshAuthState,
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
