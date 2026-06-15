import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createElement, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import i18n from '../../i18n'
import { ThemeProvider } from '../../hooks/useTheme'

const mockRefreshUser = vi.fn()
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      id: 'u1',
      email: 'a@b.c',
      display_name: 'Aisha',
      provider: 'google',
      created_at: '2026-01-01T00:00:00Z',
    },
    role: 'researcher',
    refreshUser: mockRefreshUser,
  }),
  emitSessionExpired: vi.fn(),
}))

const fetchProfile = vi.fn()
const fetchSessions = vi.fn()
const replacePreferences = vi.fn()
const updateDisplayName = vi.fn()
vi.mock('../../api/profile-client', () => ({
  fetchProfile: () => fetchProfile(),
  fetchSessions: () => fetchSessions(),
  replacePreferences: (p: unknown) => replacePreferences(p),
  updateDisplayName: (n: string) => updateDisplayName(n),
}))

import ProfilePage from '../ProfilePage'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      QueryClientProvider,
      { client: qc },
      createElement(ThemeProvider, null, children),
    )
  }
}

// The full server-stored blob, including a key this client does not model — a
// read-modify-write PUT must preserve it.
const BASE_PREFS = {
  theme: 'light',
  language: 'en',
  default_search_mode: 'semantic',
  results_per_page: 50,
  custom_key: 'keep',
}

beforeEach(() => {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
  )
  localStorage.clear()
  localStorage.setItem('isnad-graph-theme', 'light')
  fetchProfile.mockResolvedValue({ user_id: 'u1', preferences: { ...BASE_PREFS } })
  fetchSessions.mockResolvedValue([
    {
      id: 's1',
      ip_address: '1.2.3.4',
      user_agent: 'x',
      created_at: '2026-01-01T00:00:00Z',
      last_active: '2026-01-02T00:00:00Z',
      expires_at: '2026-02-01T00:00:00Z',
      is_current: false,
    },
  ])
  replacePreferences.mockImplementation((p) => Promise.resolve({ user_id: 'u1', preferences: p }))
})

afterEach(async () => {
  await act(async () => {
    await i18n.changeLanguage('en')
  })
  vi.clearAllMocks()
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('ProfilePage', () => {
  it('renders account info and drops the (stub) labels', async () => {
    render(<ProfilePage />, { wrapper: makeWrapper() })

    expect(await screen.findByText('Aisha')).toBeInTheDocument()
    expect(screen.getByText('a@b.c')).toBeInTheDocument()
    expect(screen.getByText('Google')).toBeInTheDocument()
    expect(screen.getByText('RESEARCHER')).toBeInTheDocument()
    // Controls are wired through, not stubs.
    expect(screen.getByText('Theme')).toBeInTheDocument()
    expect(screen.getByText('Language')).toBeInTheDocument()
    expect(screen.queryByText(/stub/i)).not.toBeInTheDocument()
  })

  it('Theme select reflects the live theme; a change drives it and persists the full blob', async () => {
    const user = userEvent.setup()
    render(<ProfilePage />, { wrapper: makeWrapper() })

    await screen.findByText('Aisha')
    // value=theme='light' (from localStorage) → selected option text "Light".
    const themeSelect = screen.getByDisplayValue('Light')

    await user.selectOptions(themeSelect, 'dark')

    // Drives the live theme immediately (single source of truth).
    await waitFor(() => expect(document.documentElement.getAttribute('data-theme')).toBe('dark'))
    // Persists the FULL blob with only `theme` changed (custom_key preserved).
    await waitFor(() => expect(replacePreferences).toHaveBeenCalled())
    expect(replacePreferences).toHaveBeenLastCalledWith({ ...BASE_PREFS, theme: 'dark' })
  })

  it('Language select reflects the locale; a change switches i18n and persists', async () => {
    const user = userEvent.setup()
    render(<ProfilePage />, { wrapper: makeWrapper() })

    await screen.findByText('Aisha')
    const languageSelect = screen.getByDisplayValue('English')

    await user.selectOptions(languageSelect, 'ar')

    await waitFor(() => expect(i18n.language).toBe('ar'))
    expect(replacePreferences).toHaveBeenLastCalledWith({ ...BASE_PREFS, language: 'ar' })
  })

  it('renders active sessions from the sessions endpoint', async () => {
    render(<ProfilePage />, { wrapper: makeWrapper() })
    expect(await screen.findByText('1.2.3.4')).toBeInTheDocument()
  })
})
