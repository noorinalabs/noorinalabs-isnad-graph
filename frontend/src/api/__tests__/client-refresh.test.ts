import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { fetchNarrators } from '../client'
import { SESSION_EXPIRED_EVENT } from '../../hooks/useAuth'

// Fetch-boundary regression tests for the #1016 fix: the data API client must
// attempt a token refresh (POST /auth/token/refresh, via the httpOnly refresh
// cookie) and retry the original request ONCE on a 401 before declaring the
// session expired. Only a failed refresh — a genuinely expired/revoked refresh
// cookie — may emit `session-expired`. These drive the REAL fetchJson against a
// stubbed `fetch`, so they assert the actual request sequence the mocked
// component tests can't see.

const REFRESH_URL = '/auth/token/refresh'
const NARRATORS_URL = '/api/v1/narrators'

// Origin resolution falls back to '' (same-origin) in the test env (no
// window.RUNTIME_CONFIG, no VITE_USER_SERVICE_ORIGIN), so the refresh POST
// targets a bare `/auth/token/refresh`.
function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 401 ? 'Unauthorized' : 'OK',
    json: async () => body,
  } as Response
}

const fetchMock = vi.fn()

function callsTo(substr: string): Array<{ url: string; init: RequestInit | undefined }> {
  return fetchMock.mock.calls
    .map((c) => ({ url: String(c[0]), init: c[1] as RequestInit | undefined }))
    .filter((c) => c.url.includes(substr))
}

function authHeader(init: RequestInit | undefined): string | undefined {
  return (init?.headers as Record<string, string> | undefined)?.Authorization
}

let onExpired: ReturnType<typeof vi.fn>

beforeEach(() => {
  localStorage.setItem('access_token', 'expired-token')
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockReset()
  onExpired = vi.fn()
  window.addEventListener(SESSION_EXPIRED_EVENT, onExpired)
})

afterEach(() => {
  window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired)
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('data client 401 → refresh → retry (#1016)', () => {
  it('on 401, refreshes once and retries the request — no session-expired', async () => {
    let dataCalls = 0
    fetchMock.mockImplementation((url: string) => {
      if (String(url).includes(REFRESH_URL)) {
        return Promise.resolve(jsonResponse({ access_token: 'fresh-token' }))
      }
      dataCalls += 1
      // First data call: the expired access token → 401. Retry: 200.
      return Promise.resolve(
        dataCalls === 1
          ? jsonResponse({ detail: 'token expired' }, 401)
          : jsonResponse({ items: [], total: 0, page: 1, limit: 20 }),
      )
    })

    const result = await fetchNarrators()

    expect(result).toEqual({ items: [], total: 0, page: 1, limit: 20 })
    // Exactly one refresh POST.
    expect(callsTo(REFRESH_URL)).toHaveLength(1)
    expect(callsTo(REFRESH_URL)[0]?.init?.method).toBe('POST')
    // Two data calls: the original (401) and the retry.
    const data = callsTo(NARRATORS_URL)
    expect(data).toHaveLength(2)
    // The retry carried the refreshed token (getAuthHeaders re-read localStorage).
    expect(authHeader(data[0]?.init)).toBe('Bearer expired-token')
    expect(authHeader(data[1]?.init)).toBe('Bearer fresh-token')
    // The user was NOT bounced to the login wall.
    expect(onExpired).not.toHaveBeenCalled()
  })

  it('on 401 with a failed refresh, emits session-expired and does not retry', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (String(url).includes(REFRESH_URL)) {
        // Refresh cookie genuinely expired/revoked → non-OK.
        return Promise.resolve(jsonResponse({ detail: 'refresh expired' }, 401))
      }
      return Promise.resolve(jsonResponse({ detail: 'token expired' }, 401))
    })

    await expect(fetchNarrators()).rejects.toThrow(/401/)

    expect(callsTo(REFRESH_URL)).toHaveLength(1)
    // No retry — the single data call stays at one (refresh failed).
    expect(callsTo(NARRATORS_URL)).toHaveLength(1)
    expect(onExpired).toHaveBeenCalledOnce()
  })

  it('single-flight: concurrent 401s share ONE refresh', async () => {
    let dataCalls = 0
    fetchMock.mockImplementation((url: string) => {
      if (String(url).includes(REFRESH_URL)) {
        return Promise.resolve(jsonResponse({ access_token: 'fresh-token' }))
      }
      dataCalls += 1
      // The first two (concurrent) data calls 401; their retries succeed.
      return Promise.resolve(
        dataCalls <= 2
          ? jsonResponse({ detail: 'token expired' }, 401)
          : jsonResponse({ items: [], total: 0, page: 1, limit: 20 }),
      )
    })

    const [a, b] = await Promise.all([fetchNarrators(), fetchNarrators()])

    expect(a).toEqual({ items: [], total: 0, page: 1, limit: 20 })
    expect(b).toEqual({ items: [], total: 0, page: 1, limit: 20 })
    // Both 401s collapsed into a single refresh POST.
    expect(callsTo(REFRESH_URL)).toHaveLength(1)
    // Four data calls total: two originals (401) + two retries (200).
    expect(callsTo(NARRATORS_URL)).toHaveLength(4)
    expect(onExpired).not.toHaveBeenCalled()
  })

  it('a 200 response never triggers a refresh', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ items: [], total: 0, page: 1, limit: 20 }))

    await fetchNarrators()

    expect(callsTo(REFRESH_URL)).toHaveLength(0)
    expect(onExpired).not.toHaveBeenCalled()
  })
})
