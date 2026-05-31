import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * Exercises the runtime-config resolution order used at the three
 * user-service-origin call sites (useAuth.ts, LoginPage.tsx, profile-client.ts):
 *
 *   window.RUNTIME_CONFIG?.USER_SERVICE_ORIGIN  // runtime (entrypoint-injected)
 *     || import.meta.env.VITE_USER_SERVICE_ORIGIN  // build-time (local dev)
 *     || ''                                        // same-origin fallback
 *
 * The call sites compute this as a module-level constant at import time, so we
 * mirror the expression here and drive it with different window/env states.
 * See isnad-graph#932 / deploy#245 step 5.
 */
function resolveOrigin(env: { VITE_USER_SERVICE_ORIGIN?: string }): string {
  return (
    (typeof window !== 'undefined' && window.RUNTIME_CONFIG?.USER_SERVICE_ORIGIN) ||
    env.VITE_USER_SERVICE_ORIGIN ||
    ''
  )
}

describe('runtime-config origin resolution', () => {
  beforeEach(() => {
    delete window.RUNTIME_CONFIG
  })

  afterEach(() => {
    delete window.RUNTIME_CONFIG
  })

  it('prefers window.RUNTIME_CONFIG over the build-time VITE value', () => {
    window.RUNTIME_CONFIG = { USER_SERVICE_ORIGIN: 'https://users.stg.noorinalabs.com' }
    expect(resolveOrigin({ VITE_USER_SERVICE_ORIGIN: 'https://build-time.example' })).toBe(
      'https://users.stg.noorinalabs.com',
    )
  })

  it('falls back to the build-time VITE value when RUNTIME_CONFIG is absent (local dev)', () => {
    // /runtime-config.js 404s under `npm run dev`, so window.RUNTIME_CONFIG stays undefined.
    expect(resolveOrigin({ VITE_USER_SERVICE_ORIGIN: 'https://users.local.example' })).toBe(
      'https://users.local.example',
    )
  })

  it('falls back to the build-time VITE value when RUNTIME_CONFIG has no origin set', () => {
    window.RUNTIME_CONFIG = {}
    expect(resolveOrigin({ VITE_USER_SERVICE_ORIGIN: 'https://users.local.example' })).toBe(
      'https://users.local.example',
    )
  })

  it('treats an empty runtime origin as unset and falls through (envsubst with USER_SERVICE_ORIGIN unset)', () => {
    window.RUNTIME_CONFIG = { USER_SERVICE_ORIGIN: '' }
    expect(resolveOrigin({ VITE_USER_SERVICE_ORIGIN: 'https://users.local.example' })).toBe(
      'https://users.local.example',
    )
  })

  it('resolves to same-origin ("") when neither runtime nor build-time origin is set', () => {
    expect(resolveOrigin({})).toBe('')
  })
})

describe('runtime-config module call sites', () => {
  beforeEach(() => {
    vi.resetModules()
    delete window.RUNTIME_CONFIG
  })

  afterEach(() => {
    vi.resetModules()
    delete window.RUNTIME_CONFIG
  })

  it('profile-client picks up the runtime origin set before module import', async () => {
    window.RUNTIME_CONFIG = { USER_SERVICE_ORIGIN: 'https://users.prod.noorinalabs.com' }
    // Importing after setting RUNTIME_CONFIG mirrors index.html loading
    // /runtime-config.js as the first <script>, before the module bundle.
    const mod = await import('../api/profile-client')
    // The module computes API_BASE from USER_SERVICE_ORIGIN at import time.
    // We can't read the private constant, but a fetch through it must target
    // the runtime origin — assert via a stubbed fetch.
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }))
    try {
      // fetchProfile is the public surface; it issues GET against API_BASE.
      await mod.fetchProfile()
    } catch {
      // ignore non-2xx parsing; we only care about the URL the fetch saw
    }
    const calledUrl = String(fetchSpy.mock.calls[0]?.[0] ?? '')
    expect(calledUrl).toContain('https://users.prod.noorinalabs.com')
    fetchSpy.mockRestore()
  })
})
