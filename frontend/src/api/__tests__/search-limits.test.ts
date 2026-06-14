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
const SERVER_SEMANTIC_CAP = 50 // /search/semantic -> Query(10, ge=1, le=50)

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
