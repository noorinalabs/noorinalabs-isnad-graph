import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Regression test for #1026: `fetchSubscriptionOrNull` must target the
// USER-SERVICE origin (`window.RUNTIME_CONFIG.USER_SERVICE_ORIGIN`), not the
// same-origin isnad-graph API. Subscriptions live in user-service; hitting the
// isnad-graph origin (`/api/v1/subscriptions/me`) 404'd on every authenticated
// page and silently treated every user as un-subscribed.
//
// The origin is baked into a module-level constant at import time, so each test
// sets `window.RUNTIME_CONFIG` and then imports the client via `vi.resetModules`
// + dynamic import to pick up that value.

const ORIGIN = 'https://users.example'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 404 ? 'Not Found' : 'OK',
    json: async () => body,
  } as Response
}

const fetchMock = vi.fn()

beforeEach(() => {
  localStorage.setItem('access_token', 'jwt')
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockReset()
  vi.resetModules()
  ;(window as unknown as { RUNTIME_CONFIG?: { USER_SERVICE_ORIGIN?: string } }).RUNTIME_CONFIG =
    { USER_SERVICE_ORIGIN: ORIGIN }
})

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
  delete (window as unknown as { RUNTIME_CONFIG?: unknown }).RUNTIME_CONFIG
})

describe('fetchSubscriptionOrNull origin (#1026)', () => {
  it('targets the user-service origin, not the same-origin isnad-graph API', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ tier: 'trial', status: 'trial', days_remaining: 5 }))
    const { fetchSubscriptionOrNull } = await import('../client')

    await fetchSubscriptionOrNull()

    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(`${ORIGIN}/api/v1/subscriptions/me`)
  })

  it('resolves a 404 (no subscription) to null without throwing', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'No subscription found' }, 404))
    const { fetchSubscriptionOrNull } = await import('../client')

    await expect(fetchSubscriptionOrNull()).resolves.toBeNull()
  })

  it('returns the parsed subscription body on 200', async () => {
    const body = { tier: 'active', status: 'active', days_remaining: 30 }
    fetchMock.mockResolvedValue(jsonResponse(body))
    const { fetchSubscriptionOrNull } = await import('../client')

    await expect(fetchSubscriptionOrNull()).resolves.toEqual(body)
  })
})
