import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { fetchProfile, revokeSession } from '../profile-client'
import { SESSION_EXPIRED_EVENT } from '../../hooks/useAuth'

// Fetch-boundary regression tests for the #1021 fix: the profile client must
// mirror the #1016 data-client recovery — attempt a token refresh
// (POST /auth/token/refresh, via the httpOnly refresh cookie) and retry the
// original request ONCE on a 401 before declaring the session expired. Before
// this fix a 401 on any /api/v1/users/me call (`fetchProfileJson`) or the
// `revokeSession` DELETE force-logged-out immediately, so a mid-session
// access-token expiry bounced the user out of their own profile despite a valid
// refresh cookie. These drive the REAL client against a stubbed `fetch`.

const REFRESH_URL = '/auth/token/refresh'
// Origin resolves to '' (same-origin) in the test env, so the profile URLs are bare.
const PROFILE_URL = '/api/v1/users/me/profile'
// Sessions are a sibling collection, NOT under /users/me (matches sessions.py).
const SESSIONS_URL = '/api/v1/sessions'

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

describe('profile client 401 → refresh → retry (#1021)', () => {
  it('on 401, refreshes once and retries fetchProfile — no session-expired', async () => {
    let dataCalls = 0
    fetchMock.mockImplementation((url: string) => {
      if (String(url).includes(REFRESH_URL)) {
        return Promise.resolve(jsonResponse({ access_token: 'fresh-token' }))
      }
      dataCalls += 1
      return Promise.resolve(
        dataCalls === 1
          ? jsonResponse({ detail: 'token expired' }, 401)
          : jsonResponse({ id: 'u1', email: 'a@b.c', name: 'A' }),
      )
    })

    const result = await fetchProfile()

    expect(result).toMatchObject({ id: 'u1' })
    expect(callsTo(REFRESH_URL)).toHaveLength(1)
    expect(callsTo(REFRESH_URL)[0]?.init?.method).toBe('POST')
    const data = callsTo(PROFILE_URL)
    expect(data).toHaveLength(2)
    expect(authHeader(data[0]?.init)).toBe('Bearer expired-token')
    expect(authHeader(data[1]?.init)).toBe('Bearer fresh-token')
    expect(onExpired).not.toHaveBeenCalled()
  })

  it('on 401 with a failed refresh, emits session-expired and does not retry', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (String(url).includes(REFRESH_URL)) {
        return Promise.resolve(jsonResponse({ detail: 'refresh expired' }, 401))
      }
      return Promise.resolve(jsonResponse({ detail: 'token expired' }, 401))
    })

    await expect(fetchProfile()).rejects.toThrow(/Unauthorized/)

    expect(callsTo(REFRESH_URL)).toHaveLength(1)
    expect(callsTo(PROFILE_URL)).toHaveLength(1)
    expect(onExpired).toHaveBeenCalledOnce()
  })

  it('revokeSession refreshes once and retries the DELETE on a 401', async () => {
    let dataCalls = 0
    fetchMock.mockImplementation((url: string) => {
      if (String(url).includes(REFRESH_URL)) {
        return Promise.resolve(jsonResponse({ access_token: 'fresh-token' }))
      }
      dataCalls += 1
      return Promise.resolve(
        dataCalls === 1 ? jsonResponse({ detail: 'token expired' }, 401) : jsonResponse({}, 204),
      )
    })

    await expect(revokeSession('s1')).resolves.toBeUndefined()

    expect(callsTo(REFRESH_URL)).toHaveLength(1)
    const data = callsTo(SESSIONS_URL)
    expect(data).toHaveLength(2)
    expect(data[1]?.init?.method).toBe('DELETE')
    expect(authHeader(data[1]?.init)).toBe('Bearer fresh-token')
    expect(onExpired).not.toHaveBeenCalled()
  })

  it('revokeSession emits session-expired when the refresh fails', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'unauth' }, 401))

    await expect(revokeSession('s1')).rejects.toThrow(/Unauthorized/)

    expect(callsTo(REFRESH_URL)).toHaveLength(1)
    expect(callsTo(SESSIONS_URL)).toHaveLength(1)
    expect(onExpired).toHaveBeenCalledOnce()
  })

  it('a 200 response never triggers a refresh', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: 'u1', email: 'a@b.c', name: 'A' }))

    await fetchProfile()

    expect(callsTo(REFRESH_URL)).toHaveLength(0)
    expect(onExpired).not.toHaveBeenCalled()
  })
})
