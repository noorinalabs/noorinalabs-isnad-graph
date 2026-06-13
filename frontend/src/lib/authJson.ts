/**
 * Defensive JSON reader for auth-service responses.
 *
 * When the user-service origin mis-resolves — e.g. a stale runtime-config or a
 * reverse-proxy fallback serving the SPA's `index.html` — the auth endpoints
 * can answer HTTP 200 with `text/html` instead of JSON. A bare `res.json()`
 * then throws a cryptic `Unexpected token '<'` straight at the user, and the
 * 200 status masks the misroute. This helper checks the content-type (and
 * guards the parse) so a misroute degrades to a clear "service unreachable /
 * misconfigured" message instead of a raw parse exception. It is the
 * frontend-side complement to the deploy runtime-config fix (deploy#420).
 */
export const NON_JSON_RESPONSE_MESSAGE =
  'The authentication service returned an unexpected response. ' +
  'It may be temporarily unreachable or misconfigured. Please try again later.'

export class NonJsonResponseError extends Error {
  constructor(message: string = NON_JSON_RESPONSE_MESSAGE) {
    super(message)
    this.name = 'NonJsonResponseError'
  }
}

/**
 * Parse a `Response` body as JSON, but only when it actually claims to be JSON.
 *
 * Throws `NonJsonResponseError` (carrying a user-facing message) when the
 * `Content-Type` is not `application/json`, or when the body fails to parse —
 * never the raw `SyntaxError` from `Response.json()`.
 */
export async function readJsonResponse<T = unknown>(res: Response): Promise<T> {
  const contentType = res.headers.get('content-type') ?? ''
  if (!contentType.toLowerCase().includes('application/json')) {
    throw new NonJsonResponseError()
  }
  try {
    return (await res.json()) as T
  } catch {
    throw new NonJsonResponseError()
  }
}
