import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mintSsoCookie } from '../sso-client'

// Fetch-boundary tests for the SSO-cookie mint (ig#1081 / user-service#171).
// The helper POSTs /auth/sso-cookie with the current access token and, mirroring
// the shared #1016/#1021 recovery, retries ONCE behind a token refresh on a 401
// before failing. These drive the REAL client against a stubbed `fetch`.

const REFRESH_URL = '/auth/token/refresh'
// Origin resolves to '' (same-origin) in the test env, so the URL is bare.
const SSO_URL = '/auth/sso-cookie'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 401 ? 'Unauthorized' : 'OK',
    url: 'http://localhost' + SSO_URL,
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

beforeEach(() => {
  localStorage.setItem('access_token', 'app-token')
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockReset()
})

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('mintSsoCookie', () => {
  it('POSTs /auth/sso-cookie with credentials:include and the bearer token', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ status: 'ok', cookie_name: 'nl_sso', expires_in: 300 }),
    )

    const result = await mintSsoCookie()

    expect(result).toMatchObject({ cookie_name: 'nl_sso', expires_in: 300 })
    const calls = callsTo(SSO_URL)
    expect(calls).toHaveLength(1)
    expect(calls[0]?.init?.method).toBe('POST')
    // credentials:include is mandatory so the browser stores the Set-Cookie.
    expect(calls[0]?.init?.credentials).toBe('include')
    expect(authHeader(calls[0]?.init)).toBe('Bearer app-token')
    expect(callsTo(REFRESH_URL)).toHaveLength(0)
  })

  it('on 401, refreshes once and retries with the fresh token', async () => {
    let mintCalls = 0
    fetchMock.mockImplementation((url: string) => {
      if (String(url).includes(REFRESH_URL)) {
        return Promise.resolve(jsonResponse({ access_token: 'fresh-token' }))
      }
      mintCalls += 1
      return Promise.resolve(
        mintCalls === 1
          ? jsonResponse({ detail: 'token expired' }, 401)
          : jsonResponse({ status: 'ok', cookie_name: 'nl_sso', expires_in: 300 }),
      )
    })

    const result = await mintSsoCookie()

    expect(result).toMatchObject({ cookie_name: 'nl_sso' })
    expect(callsTo(REFRESH_URL)).toHaveLength(1)
    const mints = callsTo(SSO_URL)
    expect(mints).toHaveLength(2)
    expect(authHeader(mints[0]?.init)).toBe('Bearer app-token')
    expect(authHeader(mints[1]?.init)).toBe('Bearer fresh-token')
  })

  it('throws an ApiError when the refresh fails (401 stands)', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'unauth' }, 401))

    await expect(mintSsoCookie()).rejects.toMatchObject({ status: 401 })

    expect(callsTo(REFRESH_URL)).toHaveLength(1)
    // Only the original attempt — no retry once the refresh fails.
    expect(callsTo(SSO_URL)).toHaveLength(1)
  })

  it('throws an ApiError on a 403 without attempting a refresh', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'forbidden' }, 403))

    await expect(mintSsoCookie()).rejects.toMatchObject({ status: 403 })

    expect(callsTo(REFRESH_URL)).toHaveLength(0)
    expect(callsTo(SSO_URL)).toHaveLength(1)
  })
})
