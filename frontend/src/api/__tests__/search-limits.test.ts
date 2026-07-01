import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  searchAll,
  searchSemantic,
  SEARCH_MAX_LIMIT,
  SEMANTIC_SEARCH_MAX_LIMIT,
} from '../client'

// The backend caps each search endpoint's ``limit`` query param (FastAPI
// ``Query(..., le=N)`` in ``src/api/routes/search.py``). Requesting more than
// the cap is rejected with a 422 before the query runs, which broke the full
// results page when it asked for limit=200 (#1025). These caps mirror the
// server bounds; if the server bounds change, update both sides together.
const SERVER_SEARCH_CAP = 100 // /search        -> Query(20, ge=1, le=100)
const SERVER_SEMANTIC_CAP = 100 // /search/semantic -> Query(10, ge=1, le=100) (raised from 50, ig#1147)

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: 'OK',
    json: async () => body,
  } as Response
}

const fetchMock = vi.fn()

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockReset()
  fetchMock.mockResolvedValue(jsonResponse({ results: [], total: 0 }))
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('search limit contract (#1025)', () => {
  it('the keyword-search results-page limit is within the server cap', () => {
    expect(SEARCH_MAX_LIMIT).toBeLessThanOrEqual(SERVER_SEARCH_CAP)
  })

  it('the semantic-search results-page limit is within the server cap', () => {
    expect(SEMANTIC_SEARCH_MAX_LIMIT).toBeLessThanOrEqual(SERVER_SEMANTIC_CAP)
  })

  it('searchAll sends the requested limit in the query string', async () => {
    await searchAll('prayer', SEARCH_MAX_LIMIT)
    const url = fetchMock.mock.calls[0]?.[0] as string
    expect(url).toContain('/api/v1/search?')
    expect(url).toContain(`limit=${SEARCH_MAX_LIMIT}`)
  })

  it('searchSemantic sends the requested limit in the query string', async () => {
    await searchSemantic('prayer', SEMANTIC_SEARCH_MAX_LIMIT)
    const url = fetchMock.mock.calls[0]?.[0] as string
    expect(url).toContain('/api/v1/search/semantic?')
    expect(url).toContain(`limit=${SEMANTIC_SEARCH_MAX_LIMIT}`)
  })
})


// ig#1147: the search endpoints gained real server-side pagination. The client
// helpers thread a 1-based ``page`` through to the query string so the results
// page can fetch batches beyond the first — lifting the flat 50-result ceiling.
// Pre-fix, ``searchAll``/``searchSemantic`` took no ``page`` argument and never
// sent one, so these assertions fail on pre-fix code.
describe('search pagination contract (ig#1147)', () => {
  it('searchAll defaults to page=1 when no page is given', async () => {
    await searchAll('prayer', SEARCH_MAX_LIMIT)
    const url = fetchMock.mock.calls[0]?.[0] as string
    expect(url).toContain('page=1')
  })

  it('searchSemantic defaults to page=1 when no page is given', async () => {
    await searchSemantic('prayer', SEMANTIC_SEARCH_MAX_LIMIT)
    const url = fetchMock.mock.calls[0]?.[0] as string
    expect(url).toContain('page=1')
  })

  it('searchAll sends a deep page so results past 50 are reachable', async () => {
    // page 6 at 10-per-page targets results 51-60 — past the old 50 ceiling.
    await searchAll('prayer', 10, 6)
    const url = fetchMock.mock.calls[0]?.[0] as string
    expect(url).toContain('/api/v1/search?')
    expect(url).toContain('page=6')
  })

  it('searchSemantic sends a deep page so results past 50 are reachable', async () => {
    await searchSemantic('prayer', 10, 6)
    const url = fetchMock.mock.calls[0]?.[0] as string
    expect(url).toContain('/api/v1/search/semantic?')
    expect(url).toContain('page=6')
  })
})
