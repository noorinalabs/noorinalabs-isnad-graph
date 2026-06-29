import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import LoginPage from '../LoginPage'
import { NON_JSON_RESPONSE_MESSAGE } from '../../lib/authJson'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

// Real providers response shape returned by GET /auth/providers.
function providersResponse(
  overrides: { id: string; type: string; enabled: boolean }[] = [
    { id: 'email', type: 'password', enabled: true },
    { id: 'google', type: 'oauth', enabled: true },
    { id: 'github', type: 'oauth', enabled: true },
    { id: 'apple', type: 'oauth', enabled: false },
    { id: 'facebook', type: 'oauth', enabled: false },
  ],
): Response {
  return jsonResponse({ providers: overrides })
}

// A reverse-proxy fallback / stale-runtime-config misroute: the SPA's own
// index.html served with HTTP 200 and a text/html content-type instead of the
// auth JSON. This is the deploy#420 failure class.
function htmlResponse(): Response {
  return new Response('<!DOCTYPE html><html><body>SPA shell</body></html>', {
    status: 200,
    headers: { 'Content-Type': 'text/html' },
  })
}

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <LoginPage />
    </MemoryRouter>,
  )
}

describe('LoginPage — /auth/providers object-shape parsing (#1007)', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders Google and GitHub buttons and hides apple/facebook (enabled:false)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(providersResponse())),
    )

    renderLogin()

    await waitFor(() => {
      expect(screen.getByText('Sign in with Google')).toBeInTheDocument()
      expect(screen.getByText('Sign in with GitHub')).toBeInTheDocument()
    })
    // apple and facebook are disabled — no button for them
    expect(screen.queryByText(/apple/i)).toBeNull()
    expect(screen.queryByText(/facebook/i)).toBeNull()
  })

  it('filters only enabled providers from the object response', async () => {
    // Feed the exact real-shape with only google enabled
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          providersResponse([
            { id: 'google', type: 'oauth', enabled: true },
            { id: 'github', type: 'oauth', enabled: false },
            { id: 'apple', type: 'oauth', enabled: false },
          ]),
        ),
      ),
    )

    renderLogin()

    await waitFor(() => {
      expect(screen.getByText('Sign in with Google')).toBeInTheDocument()
    })
    expect(screen.queryByText('Sign in with GitHub')).toBeNull()
  })

  it('falls back to google+github when the endpoint fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new Error('network error'))),
    )

    renderLogin()

    await waitFor(() => {
      expect(screen.getByText('Sign in with Google')).toBeInTheDocument()
      expect(screen.getByText('Sign in with GitHub')).toBeInTheDocument()
    })
  })
})

describe('LoginPage — non-JSON auth response guard (#977)', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('surfaces a clean error (not a raw parse throw) when email login is misrouted to HTML', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/auth/providers')) return Promise.resolve(providersResponse())
      if (url.endsWith('/auth/login')) return Promise.resolve(htmlResponse())
      return Promise.reject(new Error(`unexpected fetch: ${url}`))
    })
    vi.stubGlobal('fetch', fetchMock)

    renderLogin()

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'user@example.com' },
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'password123' },
    })

    const form = screen.getByLabelText('Email').closest('form') as HTMLFormElement
    fireEvent.submit(form)

    const alert = await waitFor(() => screen.getByRole('alert'))
    expect(alert).toHaveTextContent(NON_JSON_RESPONSE_MESSAGE)
    // The raw SyntaxError must never reach the user.
    expect(alert).not.toHaveTextContent(/unexpected token/i)
    // And no bogus token gets persisted from an HTML body.
    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('still completes a genuine JSON login', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/auth/providers')) return Promise.resolve(providersResponse())
      if (url.endsWith('/auth/login'))
        return Promise.resolve(jsonResponse({ access_token: 'real-token' }))
      return Promise.reject(new Error(`unexpected fetch: ${url}`))
    })
    vi.stubGlobal('fetch', fetchMock)

    renderLogin()

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'user@example.com' },
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'password123' },
    })
    fireEvent.submit(screen.getByLabelText('Email').closest('form') as HTMLFormElement)

    await waitFor(() => {
      expect(localStorage.getItem('access_token')).toBe('real-token')
    })
    expect(screen.queryByRole('alert')).toBeNull()
  })
})
