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
      if (url.endsWith('/auth/providers')) return Promise.resolve(jsonResponse(['google']))
      if (url.endsWith('/auth/login/email')) return Promise.resolve(htmlResponse())
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
      if (url.endsWith('/auth/providers')) return Promise.resolve(jsonResponse(['google']))
      if (url.endsWith('/auth/login/email'))
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
