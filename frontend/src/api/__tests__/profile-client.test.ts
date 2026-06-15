import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  fetchSessions,
  replacePreferences,
  updateDisplayName,
  type UserPreferences,
} from '../profile-client'

// Endpoint-shape regression tests reconciling the client with the merged
// user-service contract (us#165 + sessions US#7): preferences are REPLACED via
// PUT /users/me/profile, the display name is a PATCH on /users/me, and sessions
// live at /api/v1/sessions returning `{ sessions, count }` — not under /users/me.

const fetchMock = vi.fn()

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: 'OK',
    json: async () => body,
  } as Response
}

beforeEach(() => {
  localStorage.setItem('access_token', 'tok')
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockReset()
})

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('profile-client endpoints', () => {
  it('replacePreferences PUTs the full blob to /users/me/profile', async () => {
    const prefs: UserPreferences = { theme: 'dark', language: 'ar', custom_key: 'keep' }
    fetchMock.mockResolvedValue(jsonResponse({ user_id: 'u1', preferences: prefs }))

    const result = await replacePreferences(prefs)

    expect(result).toMatchObject({ user_id: 'u1' })
    const [url, init] = fetchMock.mock.calls[0]!
    expect(String(url)).toBe('/api/v1/users/me/profile')
    expect((init as RequestInit).method).toBe('PUT')
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ preferences: prefs })
  })

  it('updateDisplayName PATCHes /users/me (not the preferences blob)', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: 'u1', display_name: 'New' }))

    await updateDisplayName('New')

    const [url, init] = fetchMock.mock.calls[0]!
    expect(String(url)).toBe('/api/v1/users/me')
    expect((init as RequestInit).method).toBe('PATCH')
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ display_name: 'New' })
  })

  it('fetchSessions hits /api/v1/sessions and unwraps the rows', async () => {
    const rows = [
      {
        id: 's1',
        ip_address: '1.2.3.4',
        user_agent: 'x',
        created_at: 'c',
        last_active: 'l',
        expires_at: 'e',
        is_current: true,
      },
    ]
    fetchMock.mockResolvedValue(jsonResponse({ sessions: rows, count: 1 }))

    const result = await fetchSessions()

    expect(String(fetchMock.mock.calls[0]![0])).toBe('/api/v1/sessions')
    expect(result).toEqual(rows)
  })
})
