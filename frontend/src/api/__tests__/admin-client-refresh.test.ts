import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  fetchSystemHealth,
  fetchAdminUser,
  resetStage,
  ResetError,
} from '../admin-client'
import { SESSION_EXPIRED_EVENT } from '../../hooks/useAuth'

// Fetch-boundary regression tests for the #1021 fix: the admin clients must
// mirror the #1016 data-client recovery — attempt a token refresh
// (POST /auth/token/refresh, via the httpOnly refresh cookie) and retry the
// original request ONCE on a 401 before declaring the session expired. Before
// this fix every admin 401 (isnad-graph admin API via `fetchAdminJson`,
// user-service admin API via `fetchUserServiceJson`, and the cross-service
// pipeline reset via `postReset`) force-logged-out immediately, so a mid-session
// access-token expiry bounced admins despite a valid refresh cookie. These drive
// the REAL clients against a stubbed `fetch`, asserting the actual request
// sequence the mocked component tests can't see.

const REFRESH_URL = '/auth/token/refresh'
// In the test env (no window.RUNTIME_CONFIG / VITE_USER_SERVICE_ORIGIN) the
// origin resolves to '' (same-origin), so the user-service + admin URLs are bare.
const HEALTH_URL = '/api/v1/admin/health/ready'
const USERS_URL = '/api/v1/users'
const RESET_STAGE_URL = '/admin/reset/stage'

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

describe('admin client (isnad-graph admin API) 401 → refresh → retry (#1021)', () => {
  it('on 401, refreshes once and retries — no session-expired', async () => {
    let dataCalls = 0
    fetchMock.mockImplementation((url: string) => {
      if (String(url).includes(REFRESH_URL)) {
        return Promise.resolve(jsonResponse({ access_token: 'fresh-token' }))
      }
      dataCalls += 1
      return Promise.resolve(
        dataCalls === 1
          ? jsonResponse({ detail: 'token expired' }, 401)
          : jsonResponse({ status: 'ok' }),
      )
    })

    const result = await fetchSystemHealth()

    expect(result).toEqual({ status: 'ok' })
    expect(callsTo(REFRESH_URL)).toHaveLength(1)
    expect(callsTo(REFRESH_URL)[0]?.init?.method).toBe('POST')
    const data = callsTo(HEALTH_URL)
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

    await expect(fetchSystemHealth()).rejects.toThrow(/admin access required/)

    expect(callsTo(REFRESH_URL)).toHaveLength(1)
    expect(callsTo(HEALTH_URL)).toHaveLength(1)
    expect(onExpired).toHaveBeenCalledOnce()
  })
})

describe('admin client (user-service admin API) 401 → refresh → retry (#1021)', () => {
  it('on 401, refreshes once and retries — no session-expired', async () => {
    let dataCalls = 0
    fetchMock.mockImplementation((url: string) => {
      if (String(url).includes(REFRESH_URL)) {
        return Promise.resolve(jsonResponse({ access_token: 'fresh-token' }))
      }
      dataCalls += 1
      return Promise.resolve(
        dataCalls === 1
          ? jsonResponse({ detail: 'token expired' }, 401)
          : jsonResponse({ id: 'u1', email: 'a@b.c' }),
      )
    })

    const result = await fetchAdminUser('u1')

    expect(result).toMatchObject({ id: 'u1' })
    expect(callsTo(REFRESH_URL)).toHaveLength(1)
    const data = callsTo(USERS_URL)
    expect(data).toHaveLength(2)
    expect(authHeader(data[1]?.init)).toBe('Bearer fresh-token')
    expect(onExpired).not.toHaveBeenCalled()
  })

  it('on 401 with a failed refresh, emits session-expired', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'unauth' }, 401))

    await expect(fetchAdminUser('u1')).rejects.toThrow(/admin access required/)

    expect(callsTo(REFRESH_URL)).toHaveLength(1)
    expect(callsTo(USERS_URL)).toHaveLength(1)
    expect(onExpired).toHaveBeenCalledOnce()
  })
})

describe('admin client (cross-service pipeline reset) 401 → refresh → retry (#1021)', () => {
  it('on 401, refreshes once and retries — no session-expired', async () => {
    let dataCalls = 0
    fetchMock.mockImplementation((url: string) => {
      if (String(url).includes(REFRESH_URL)) {
        return Promise.resolve(jsonResponse({ access_token: 'fresh-token' }))
      }
      dataCalls += 1
      return Promise.resolve(
        dataCalls === 1
          ? jsonResponse({ detail: 'token expired' }, 401)
          : jsonResponse({ ok: true, dry_run: true, deleted: {} }),
      )
    })

    const result = await resetStage('raw', true)

    expect(result).toMatchObject({ ok: true })
    expect(callsTo(REFRESH_URL)).toHaveLength(1)
    expect(callsTo(RESET_STAGE_URL)).toHaveLength(2)
    expect(onExpired).not.toHaveBeenCalled()
  })

  it('on 401 with a failed refresh, emits session-expired and throws ResetError(401)', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'unauth' }, 401))

    await expect(resetStage('raw', true)).rejects.toMatchObject({
      name: 'ResetError',
      status: 401,
    })
    // Sanity: the rejection is the typed ResetError, not a generic throw.
    await expect(resetStage('raw', true)).rejects.toBeInstanceOf(ResetError)

    expect(onExpired).toHaveBeenCalled()
  })
})

describe('admin clients: a 200 response never triggers a refresh (#1021)', () => {
  it('fetchSystemHealth', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: 'ok' }))

    await fetchSystemHealth()

    expect(callsTo(REFRESH_URL)).toHaveLength(0)
    expect(onExpired).not.toHaveBeenCalled()
  })
})
