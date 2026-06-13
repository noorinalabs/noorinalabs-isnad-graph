import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { MockInstance } from 'vitest'

import { ApiError, apiError } from '../api-error'
import en from '../../i18n/locales/en.json'
import { fetchNarrators } from '../client'
import { fetchContentStats } from '../admin-client'
import { fetchProfile } from '../profile-client'

// ig#1017: the API clients used to `throw new Error(`API error: ${status}
// ${statusText}`)`, and the page error states render `error.message` verbatim,
// so users saw "Error: API error: 401". These tests pin the fix: the UI-facing
// `message` is friendly i18n copy, the raw status is kept off the rendered
// surface (on `.detail` / logged to console only), and every client boundary
// routes its non-OK throw through `apiError`.

// A bare object is enough for the helper — it only reads status/statusText/url.
function res(status: number, statusText: string, url = 'https://x/api'): Response {
  return { status, statusText, url } as Response
}

describe('apiError / ApiError', () => {
  let errorSpy: MockInstance<typeof console.error>

  beforeEach(() => {
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    errorSpy.mockRestore()
  })

  it('maps status classes to friendly, localized copy (never the raw status)', () => {
    const cases: Array<[number, string]> = [
      [401, en.errors.apiSessionExpired],
      [403, en.errors.apiForbidden],
      [404, en.errors.apiNotFound],
      [429, en.errors.apiRateLimited],
      [500, en.errors.apiServer],
      [503, en.errors.apiServer],
      [418, en.errors.apiGeneric],
    ]
    for (const [status, expected] of cases) {
      const err = apiError(res(status, 'Whatever'))
      expect(err).toBeInstanceOf(ApiError)
      expect(err.message).toBe(expected)
      // The raw status / statusText must NOT leak into the user-facing message.
      expect(err.message).not.toContain(String(status))
      expect(err.message).not.toContain('API error')
      expect(err.message).not.toContain('Whatever')
    }
  })

  it('preserves the raw HTTP detail off the rendered surface (status/detail)', () => {
    const err = apiError(res(404, 'Not Found'))
    expect(err.status).toBe(404)
    expect(err.statusText).toBe('Not Found')
    expect(err.detail).toBe('404 Not Found')
    expect(err.name).toBe('ApiError')
  })

  it('logs the raw detail to the console for devtools (not to the UI)', () => {
    apiError(res(500, 'Internal Server Error', 'https://x/api/v1/narrators'))
    expect(errorSpy).toHaveBeenCalledTimes(1)
    const logged = String(errorSpy.mock.calls[0]?.[0] ?? '')
    expect(logged).toContain('500 Internal Server Error')
    expect(logged).toContain('https://x/api/v1/narrators')
  })
})

describe('client boundaries surface friendly errors (no raw status leak)', () => {
  let fetchSpy: MockInstance<typeof globalThis.fetch>
  let errorSpy: MockInstance<typeof console.error>

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch')
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    fetchSpy.mockRestore()
    errorSpy.mockRestore()
  })

  function errResponse(status: number, statusText: string): Response {
    return { ok: false, status, statusText, url: 'https://x/api', json: async () => ({}) } as Response
  }

  it('client.ts: 404 throws the friendly not-found copy, not "API error: 404"', async () => {
    fetchSpy.mockResolvedValue(errResponse(404, 'Not Found'))
    await expect(fetchNarrators(1, 20)).rejects.toMatchObject({
      message: en.errors.apiNotFound,
      status: 404,
    })
    await expect(fetchNarrators(1, 20)).rejects.not.toThrow(/API error/)
  })

  it('admin-client.ts: 500 throws the friendly server copy', async () => {
    fetchSpy.mockResolvedValue(errResponse(500, 'Internal Server Error'))
    await expect(fetchContentStats()).rejects.toMatchObject({
      message: en.errors.apiServer,
      status: 500,
    })
  })

  it('profile-client.ts: 500 throws the friendly server copy', async () => {
    fetchSpy.mockResolvedValue(errResponse(500, 'Internal Server Error'))
    await expect(fetchProfile()).rejects.toMatchObject({
      message: en.errors.apiServer,
      status: 500,
    })
  })
})
