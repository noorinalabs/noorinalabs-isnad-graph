/**
 * Unit coverage for the stg smoke auth pre-flight (ig#1146).
 *
 * The stg smoke suite (`tests/stg-smoke/`) only runs on dispatch/schedule
 * against a deployed app, so its loud-fail behavior would otherwise be
 * unprovable in PR CI. This vitest test exercises the pure decision function
 * DIRECTLY so CI proves — with no live stg env — that a missing-creds harness
 * fails RED under `requireAuth` instead of silently skipping.
 */
import { describe, it, expect } from 'vitest'
import { evaluateAuthPreflight, HarnessConfigError } from '../../tests/stg-smoke/preflight'

const base = {
  baseUrl: 'https://isnad.stg.noorinalabs.com',
  userServiceUrl: 'https://users.stg.noorinalabs.com',
  email: '',
  password: '',
  requireAuth: false,
}

describe('evaluateAuthPreflight (ig#1146 loud-fail)', () => {
  it('returns { action: "login" } when both creds are present', () => {
    expect(
      evaluateAuthPreflight({ ...base, email: 'qa@example.com', password: 'pw' }),
    ).toEqual({ action: 'login' })
  })

  it('soft-skips when creds are absent and auth is not required', () => {
    const decision = evaluateAuthPreflight(base)
    expect(decision.action).toBe('skip')
    if (decision.action === 'skip') {
      expect(decision.reason).toMatch(/soft-skipped/i)
    }
  })

  it('THROWS (loud RED) when creds are absent but auth is required', () => {
    expect(() => evaluateAuthPreflight({ ...base, requireAuth: true })).toThrow(
      HarnessConfigError,
    )
  })

  it('THROWS when only one credential is present and auth is required', () => {
    expect(() =>
      evaluateAuthPreflight({ ...base, email: 'qa@example.com', requireAuth: true }),
    ).toThrow(HarnessConfigError)
  })

  it('throws on an empty base URL regardless of requireAuth', () => {
    expect(() => evaluateAuthPreflight({ ...base, baseUrl: '' })).toThrow(HarnessConfigError)
    expect(() =>
      evaluateAuthPreflight({
        ...base,
        baseUrl: '',
        email: 'qa@example.com',
        password: 'pw',
      }),
    ).toThrow(HarnessConfigError)
  })

  it('throws on an empty (whitespace-only) user-service URL', () => {
    expect(() => evaluateAuthPreflight({ ...base, userServiceUrl: '  ' })).toThrow(
      HarnessConfigError,
    )
  })
})
