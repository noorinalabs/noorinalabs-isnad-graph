import { describe, it, expect } from 'vitest'

import {
  readJsonResponse,
  NonJsonResponseError,
  NON_JSON_RESPONSE_MESSAGE,
} from '../authJson'

describe('readJsonResponse', () => {
  it('parses a genuine application/json response', async () => {
    const res = new Response(JSON.stringify({ access_token: 'abc' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
    await expect(readJsonResponse<{ access_token: string }>(res)).resolves.toEqual({
      access_token: 'abc',
    })
  })

  it('honours a charset-suffixed JSON content-type', async () => {
    const res = new Response(JSON.stringify([{ a: 1 }]), {
      status: 200,
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    })
    await expect(readJsonResponse(res)).resolves.toEqual([{ a: 1 }])
  })

  it('throws NonJsonResponseError on a 200 text/html body (the deploy#420 misroute)', async () => {
    // A reverse-proxy fallback serving the SPA index.html with HTTP 200.
    const res = new Response('<!DOCTYPE html><html><body>SPA</body></html>', {
      status: 200,
      headers: { 'Content-Type': 'text/html' },
    })
    await expect(readJsonResponse(res)).rejects.toBeInstanceOf(NonJsonResponseError)
    await expect(readJsonResponse(res)).rejects.toThrow(NON_JSON_RESPONSE_MESSAGE)
  })

  it('throws NonJsonResponseError when content-type is absent', async () => {
    const res = new Response('not json', { status: 200 })
    res.headers.delete('content-type')
    await expect(readJsonResponse(res)).rejects.toBeInstanceOf(NonJsonResponseError)
  })

  it('throws NonJsonResponseError when the body claims JSON but fails to parse', async () => {
    const res = new Response('<<< not json >>>', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
    await expect(readJsonResponse(res)).rejects.toBeInstanceOf(NonJsonResponseError)
  })

  it('never leaks the raw SyntaxError ("Unexpected token") to the caller', async () => {
    const res = new Response('<!DOCTYPE html>', {
      status: 200,
      headers: { 'Content-Type': 'text/html' },
    })
    await expect(readJsonResponse(res)).rejects.not.toThrow(/unexpected token/i)
  })
})
