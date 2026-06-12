import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { MockInstance } from 'vitest'
import { resetStage, resetSource, resetFull, ResetError } from '../admin-client'

// Fetch-boundary tests for the cross-service reset client. Unlike the
// component tests (which vi.mock the client), these exercise the REAL
// resetFull/resetStage/resetSource against a stubbed `fetch`, so they assert
// the actual request shape and status→error mapping. This is the regression
// guard for the ingest#73 contract: the full reset's `confirmation` is a
// REQUIRED field (extra="forbid"), so a token-less {dry_run:true} body 422s
// before the handler runs — a bug the mocked component tests could not catch.

function okResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function errResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

let fetchSpy: MockInstance<typeof globalThis.fetch>

beforeEach(() => {
  fetchSpy = vi.spyOn(globalThis, 'fetch')
})

afterEach(() => {
  fetchSpy.mockRestore()
})

function lastRequest(): { url: string; body: Record<string, unknown> } {
  const call = fetchSpy.mock.calls[0]
  const url = String(call?.[0] ?? '')
  const init = (call?.[1] ?? {}) as RequestInit
  return { url, body: JSON.parse(String(init.body ?? '{}')) }
}

describe('reset client — request shape at the fetch boundary', () => {
  it('full dry-run sends the OBLITERATE token (ingest#73 requires confirmation even on dry-run)', async () => {
    fetchSpy.mockResolvedValue(
      okResponse({
        level: 'full',
        dry_run: true,
        confirmation_method: 'typed_token',
        audit_entry_path: '/audit/x.json',
        summary: {},
      }),
    )

    await resetFull('OBLITERATE', true)

    const { url, body } = lastRequest()
    expect(url).toContain('/admin/reset/full')
    // The token MUST be present on the dry-run, or the backend 422s.
    expect(body).toEqual({ confirmation: 'OBLITERATE', dry_run: true })
  })

  it('full real-run sends the OBLITERATE token with dry_run:false', async () => {
    fetchSpy.mockResolvedValue(
      okResponse({
        level: 'full',
        dry_run: false,
        confirmation_method: 'typed_token',
        audit_entry_path: '/audit/x.json',
        summary: {},
      }),
    )

    await resetFull('OBLITERATE', false)

    expect(lastRequest().body).toEqual({ confirmation: 'OBLITERATE', dry_run: false })
  })

  it('REGRESSION: a token-less full request 422s — the exact shape that hid behind the mock', async () => {
    // A 422 is what ingest#73 returns for a missing `confirmation` field. The
    // pre-fix UI produced precisely this {dry_run:true} (no token) body, so the
    // full reset was dead on arrival. This test fails loudly if anyone reverts
    // to omitting the token.
    fetchSpy.mockResolvedValue(errResponse(422, { detail: 'field required: confirmation' }))

    await expect(resetFull('', true)).rejects.toBeInstanceOf(ResetError)

    // Prove the rejected shape is the token-less body (no `confirmation` key).
    expect(lastRequest().body).toEqual({ dry_run: true })
  })

  it('stage reset posts {stage, dry_run} to /admin/reset/stage', async () => {
    fetchSpy.mockResolvedValue(
      okResponse({
        level: 'stage',
        dry_run: true,
        confirmation_method: 'dry_run',
        audit_entry_path: '/audit/x.json',
        summary: {},
      }),
    )

    await resetStage('normalized', true)

    const { url, body } = lastRequest()
    expect(url).toContain('/admin/reset/stage')
    expect(body).toEqual({ stage: 'normalized', dry_run: true })
  })

  it('source reset posts {source, dry_run} to /admin/reset/source', async () => {
    fetchSpy.mockResolvedValue(
      okResponse({
        level: 'source',
        dry_run: false,
        confirmation_method: 'explicit',
        audit_entry_path: '/audit/x.json',
        summary: {},
      }),
    )

    await resetSource('sunnah', false)

    const { url, body } = lastRequest()
    expect(url).toContain('/admin/reset/source')
    expect(body).toEqual({ source: 'sunnah', dry_run: false })
  })
})

describe('reset client — status → ResetError mapping', () => {
  it.each([
    [400, /confirmation missing or incorrect/i],
    [403, /requires an admin account/i],
    [422, /Validation error/i],
    [503, /JWKS/i],
  ])('maps HTTP %i to a ResetError carrying that status', async (status, messageRe) => {
    fetchSpy.mockResolvedValue(errResponse(status, {}))
    try {
      await resetStage('raw', true)
      throw new Error('expected resetStage to throw')
    } catch (err) {
      expect(err).toBeInstanceOf(ResetError)
      expect((err as ResetError).status).toBe(status)
      expect((err as ResetError).message).toMatch(messageRe)
    }
  })

  it('prefers a server-provided `detail` on a 422', async () => {
    fetchSpy.mockResolvedValue(errResponse(422, { detail: 'unknown stage: bogus' }))
    await expect(resetStage('raw', true)).rejects.toMatchObject({
      status: 422,
      message: 'unknown stage: bogus',
    })
  })
})
