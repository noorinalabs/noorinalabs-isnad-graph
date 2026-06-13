import i18n from '../i18n'

// A typed error thrown at the API-client boundary. The page-level error states
// render `error.message` verbatim (e.g. `Error: {(error as Error).message}`), so
// the raw `${status} ${statusText}` must NEVER land in `message` — that is the
// leak ig#1017 fixes ("Error: API error: 401"). Instead `message` is a friendly,
// actionable, localized string mapped from the status class, while the raw HTTP
// detail is preserved on `.status` / `.statusText` / `.detail` for callers and
// devtools, and echoed to the console for triage.
export class ApiError extends Error {
  readonly status: number
  readonly statusText: string
  /** Raw `${status} ${statusText}` — for logs/devtools only, never user-facing. */
  readonly detail: string

  constructor(status: number, statusText: string) {
    super(friendlyMessage(status))
    this.name = 'ApiError'
    this.status = status
    this.statusText = statusText
    this.detail = `${status} ${statusText}`.trim()
  }
}

// Map an HTTP status onto friendly, actionable user-facing copy. Routed through
// i18next (the `errors.*` catalog) so the message follows the active UI locale,
// the same as every other user-facing string. English is the fallback locale.
function friendlyMessage(status: number): string {
  const key =
    status === 401
      ? 'errors.apiSessionExpired'
      : status === 403
        ? 'errors.apiForbidden'
        : status === 404
          ? 'errors.apiNotFound'
          : status === 429
            ? 'errors.apiRateLimited'
            : status >= 500
              ? 'errors.apiServer'
              : 'errors.apiGeneric'
  return i18n.t(key)
}

/**
 * Build an {@link ApiError} from a non-OK `Response`. The raw status is echoed
 * to the console so it stays available for devtools/triage without ever
 * surfacing to the rendered UI.
 */
export function apiError(res: Response): ApiError {
  const err = new ApiError(res.status, res.statusText)
  console.error(`API error: ${err.detail} (${res.url || 'request'})`)
  return err
}
