import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import i18n from '../../i18n'
import { ThemeProvider } from '../useTheme'

// Controllable auth + profile mocks. The hook is the server→client bridge that
// makes login the source of truth for theme/locale (#1044) while leaving the
// anonymous path on localStorage.
let mockUser: { id: string } | null = null
vi.mock('../useAuth', () => ({
  useAuth: () => ({ user: mockUser }),
  emitSessionExpired: vi.fn(),
}))

const fetchProfile = vi.fn()
vi.mock('../../api/profile-client', () => ({
  fetchProfile: () => fetchProfile(),
}))

import { useProfilePreferenceSync } from '../useProfilePreferenceSync'

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

beforeEach(() => {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
  )
  localStorage.clear()
  fetchProfile.mockReset()
  mockUser = null
})

afterEach(async () => {
  await act(async () => {
    await i18n.changeLanguage('en')
  })
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('useProfilePreferenceSync', () => {
  it('hydrates the live theme + locale from the server on login', async () => {
    mockUser = { id: 'u1' }
    fetchProfile.mockResolvedValue({
      user_id: 'u1',
      preferences: { theme: 'dark', language: 'ar' },
    })

    renderHook(() => useProfilePreferenceSync(), { wrapper: makeWrapper() })

    await waitFor(() => expect(localStorage.getItem('isnad-graph-theme')).toBe('dark'))
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    await waitFor(() => expect(i18n.language).toBe('ar'))
  })

  it('leaves an anonymous session on localStorage (no fetch, no override)', async () => {
    mockUser = null
    localStorage.setItem('isnad-graph-theme', 'light')

    renderHook(() => useProfilePreferenceSync(), { wrapper: makeWrapper() })

    expect(fetchProfile).not.toHaveBeenCalled()
    expect(localStorage.getItem('isnad-graph-theme')).toBe('light')
    expect(i18n.language).toBe('en')
  })

  it('ignores an unsupported server locale rather than switching to it', async () => {
    mockUser = { id: 'u2' }
    fetchProfile.mockResolvedValue({
      user_id: 'u2',
      preferences: { theme: 'light', language: 'xx-not-a-locale' },
    })

    renderHook(() => useProfilePreferenceSync(), { wrapper: makeWrapper() })

    await waitFor(() => expect(localStorage.getItem('isnad-graph-theme')).toBe('light'))
    expect(i18n.language).toBe('en')
  })
})
