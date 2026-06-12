import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  fetchAdminUsers,
  fetchAdminUser,
  fetchRoles,
  assignUserRole,
  removeUserRole,
  deactivateUser,
  setUserRole,
  type Role,
} from '../admin-client'
import { SESSION_EXPIRED_EVENT } from '../../hooks/useAuth'

// Origin resolution falls back to '' (same-origin) in the test env (no
// window.RUNTIME_CONFIG, no VITE_USER_SERVICE_ORIGIN), so every user-service
// call targets a bare `/api/v1/...` path.
const USERS = '/api/v1/users'
const ROLES = '/api/v1/roles'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: 'OK',
    json: async () => body,
  } as Response
}

function noContent(): Response {
  return { ok: true, status: 204, statusText: 'No Content', json: async () => undefined } as Response
}

const fetchMock = vi.fn()

// Safe accessor — tsconfig enables noUncheckedIndexedAccess, so a bare
// `fetchMock.mock.calls[i][0]` is typed as possibly-undefined.
function nthCall(i: number): { url: string; init: RequestInit | undefined } {
  const c = fetchMock.mock.calls[i]
  if (!c) throw new Error(`no fetch call at index ${i}`)
  return { url: c[0] as string, init: c[1] as RequestInit | undefined }
}

beforeEach(() => {
  localStorage.setItem('access_token', 'admin-jwt')
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockReset()
})

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('admin-client user-service calls', () => {
  it('fetchAdminUsers targets the user-service list with limit and cursor', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ items: [], next_cursor: null }))
    await fetchAdminUsers('cur-123', 20)
    const { url } = nthCall(0)
    expect(url).toContain(USERS)
    expect(url).toContain('limit=20')
    expect(url).toContain('cursor=cur-123')
  })

  it('fetchAdminUsers omits the cursor param on the first page', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ items: [], next_cursor: null }))
    await fetchAdminUsers(null, 20)
    expect(nthCall(0).url).not.toContain('cursor=')
  })

  it('sends the admin Bearer JWT and does NOT set credentials:include', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ items: [], next_cursor: null }))
    await fetchAdminUsers(null, 20)
    const { init } = nthCall(0)
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer admin-jwt')
    expect(init?.credentials).toBeUndefined()
  })

  it('fetchAdminUser targets the by-id endpoint', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: 'u1', email: 'a@b.c' }))
    await fetchAdminUser('u1')
    expect(nthCall(0).url).toBe(`${USERS}/u1`)
  })

  it('fetchRoles reads the role catalog', async () => {
    fetchMock.mockResolvedValue(jsonResponse([]))
    await fetchRoles()
    expect(nthCall(0).url).toBe(ROLES)
  })

  it('assignUserRole POSTs the role_id', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: 'r1', name: 'admin' }))
    await assignUserRole('u1', 'r1')
    const { url, init } = nthCall(0)
    expect(url).toBe(`${USERS}/u1/roles`)
    expect(init?.method).toBe('POST')
    expect(JSON.parse(init?.body as string)).toEqual({ role_id: 'r1' })
  })

  it('removeUserRole DELETEs the assignment and resolves on 204', async () => {
    fetchMock.mockResolvedValue(noContent())
    await expect(removeUserRole('u1', 'r1')).resolves.toBeUndefined()
    const { url, init } = nthCall(0)
    expect(url).toBe(`${USERS}/u1/roles/r1`)
    expect(init?.method).toBe('DELETE')
  })

  it('deactivateUser soft-deletes via DELETE on the user', async () => {
    fetchMock.mockResolvedValue(noContent())
    await deactivateUser('u1')
    const { url, init } = nthCall(0)
    expect(url).toBe(`${USERS}/u1`)
    expect(init?.method).toBe('DELETE')
  })

  it('throws an admin-access error on 403', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'forbidden' }, 403))
    await expect(fetchAdminUsers(null, 20)).rejects.toThrow(/admin access required/)
  })

  it('emits the session-expired event on 401', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'unauth' }, 401))
    const onExpired = vi.fn()
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired)
    await expect(fetchAdminUser('u1')).rejects.toThrow(/admin access required/)
    expect(onExpired).toHaveBeenCalledOnce()
    window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired)
  })
})

describe('setUserRole (single-role switch over the additive role API)', () => {
  const catalog: Role[] = [
    { id: 'r-trial', name: 'trial', description: null, created_at: '2026-01-01T00:00:00Z' },
    { id: 'r-reader', name: 'reader', description: null, created_at: '2026-01-01T00:00:00Z' },
    { id: 'r-admin', name: 'admin', description: null, created_at: '2026-01-01T00:00:00Z' },
  ]

  it('assigns the target and removes every other held role', async () => {
    fetchMock.mockResolvedValue(noContent())
    // user currently holds 'reader'; switch to 'admin'
    await setUserRole('u1', 'admin', ['reader'], catalog)

    // POST assign admin, then DELETE remove reader (NOT trial — user lacks it)
    expect(fetchMock.mock.calls).toHaveLength(2)
    const assign = nthCall(0)
    expect(assign.url).toBe(`${USERS}/u1/roles`)
    expect(assign.init?.method).toBe('POST')
    expect(JSON.parse(assign.init?.body as string)).toEqual({ role_id: 'r-admin' })
    const remove = nthCall(1)
    expect(remove.url).toBe(`${USERS}/u1/roles/r-reader`)
    expect(remove.init?.method).toBe('DELETE')
  })

  it('does not re-assign a role the user already holds', async () => {
    fetchMock.mockResolvedValue(noContent())
    // user already 'admin' and also 'reader'; re-selecting 'admin' just strips reader
    await setUserRole('u1', 'admin', ['admin', 'reader'], catalog)
    expect(fetchMock.mock.calls).toHaveLength(1)
    const remove = nthCall(0)
    expect(remove.url).toBe(`${USERS}/u1/roles/r-reader`)
    expect(remove.init?.method).toBe('DELETE')
  })

  it('throws when the target role is not in the catalog', async () => {
    await expect(setUserRole('u1', 'wizard', ['reader'], catalog)).rejects.toThrow(/Unknown role/)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
