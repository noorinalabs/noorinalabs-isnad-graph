import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'

type Theme = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'isnad-graph-theme'

export interface ThemeContextValue {
  theme: Theme
  resolvedTheme: 'light' | 'dark'
  setTheme: (theme: Theme) => void
  toggle: () => void
}

function getSystemTheme(): 'light' | 'dark' {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme: Theme) {
  const resolved = theme === 'system' ? getSystemTheme() : theme
  document.documentElement.setAttribute('data-theme', resolved)
}

function readStoredTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'light' || stored === 'dark' || stored === 'system') return stored
  return 'system'
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

/**
 * Holds the single, app-wide theme state. Mounted once near the root so every
 * consumer — the header toggle, the user menu, the Profile selector, and the
 * login-time server hydration — reads and writes the same value. Previously each
 * caller spun up its own `useState`, so the Profile "Theme" control could never
 * be a real source of truth for the live theme (#1013/#1044).
 *
 * localStorage (`isnad-graph-theme`) remains the persistence layer and the
 * anonymous/offline fallback; server hydration on login simply calls `setTheme`,
 * which writes through to it (last-writer-wins).
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readStoredTheme)

  const setTheme = useCallback((newTheme: Theme) => {
    setThemeState(newTheme)
    localStorage.setItem(STORAGE_KEY, newTheme)
    applyTheme(newTheme)
  }, [])

  // Apply on mount and listen for system changes
  useEffect(() => {
    applyTheme(theme)

    if (theme === 'system') {
      const mq = window.matchMedia('(prefers-color-scheme: dark)')
      const handler = () => applyTheme('system')
      mq.addEventListener('change', handler)
      return () => mq.removeEventListener('change', handler)
    }
  }, [theme])

  const toggle = useCallback(() => {
    setTheme(
      theme === 'dark'
        ? 'light'
        : theme === 'light'
          ? 'dark'
          : getSystemTheme() === 'dark'
            ? 'light'
            : 'dark',
    )
  }, [theme, setTheme])

  const resolvedTheme = theme === 'system' ? getSystemTheme() : theme

  return createElement(
    ThemeContext.Provider,
    { value: { theme, resolvedTheme, setTheme, toggle } },
    children,
  )
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (ctx === null) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return ctx
}
