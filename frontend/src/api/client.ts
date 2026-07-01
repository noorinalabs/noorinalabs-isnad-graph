import type {
  PaginatedResponse,
  Narrator,
  Hadith,
  HadithFacetsResponse,
  Collection,
  NarratorChainsResponse,
  ChainVisualization,
  SearchResultsResponse,
  SubscriptionResponse,
  TimelineResponse,
  TimelineRangeResponse,
  ParallelsResponse,
  ParallelPairsResponse,
  NarratorNetworkResponse,
  ModerationItem,
  SystemReport,
} from '../types/api'

import { emitSessionExpired } from '../hooks/useAuth'
import { getAuthHeaders } from './auth-headers'
import { refreshAccessToken } from './token-refresh'
import { apiError } from './api-error'

const API_BASE = '/api/v1'

// Subscriptions live in the user-service, not the isnad-graph API. Resolve its
// origin at runtime from `window.RUNTIME_CONFIG` (injected by the container
// entrypoint), falling back to the build-time `VITE_USER_SERVICE_ORIGIN`, then
// to same-origin. This mirrors useAuth.ts / profile-client.ts / admin-client.ts.
// Without this, `/subscriptions/me` hit the isnad-graph origin — which has no
// such route — and 404'd on every authenticated page, silently treating every
// user (including real subscribers) as un-subscribed. (#1026)
const USER_SERVICE_ORIGIN =
  (typeof window !== 'undefined' && window.RUNTIME_CONFIG?.USER_SERVICE_ORIGIN) ||
  import.meta.env.VITE_USER_SERVICE_ORIGIN ||
  ''
const SUBSCRIPTIONS_BASE = `${USER_SERVICE_ORIGIN}/api/v1/subscriptions`

async function fetchJson<T>(url: string): Promise<T> {
  let res = await fetch(url, { headers: getAuthHeaders(), credentials: 'include' })
  if (res.status === 401) {
    // The access token has likely expired mid-session. Try a single refresh
    // (shared across concurrent 401s) and retry the request ONCE with the new
    // token before giving up — only a genuinely expired/revoked refresh cookie
    // forces the session-expired modal. getAuthHeaders() re-reads the freshly
    // persisted token. (#1016)
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      res = await fetch(url, { headers: getAuthHeaders(), credentials: 'include' })
    }
    if (res.status === 401) {
      emitSessionExpired()
    }
  }
  if (!res.ok) {
    throw apiError(res)
  }
  return res.json() as Promise<T>
}

export async function fetchNarrators(
  page = 1,
  limit = 20,
  search?: string,
): Promise<PaginatedResponse<Narrator>> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (search) params.set('q', search)
  return fetchJson(`${API_BASE}/narrators?${params}`)
}

export async function fetchNarrator(id: string): Promise<Narrator> {
  return fetchJson(`${API_BASE}/narrators/${encodeURIComponent(id)}`)
}

export async function fetchNarratorChains(id: string): Promise<NarratorChainsResponse> {
  return fetchJson(`${API_BASE}/graph/narrator/${encodeURIComponent(id)}/chains`)
}

// The ordered isnad chain for a single hadith (nodes + edges, edges carry
// `position` so the consumer can render in transmission order). #1032.
export async function fetchHadithChain(hadithId: string): Promise<ChainVisualization> {
  return fetchJson(`${API_BASE}/graph/hadith/${encodeURIComponent(hadithId)}/chain`)
}

export async function fetchHadiths(
  page = 1,
  limit = 20,
  filters?: {
    collection?: string
    source_corpus?: string
    grade?: string
    q?: string
    // Narrator id — filter to hadiths whose isnad contains this narrator. #1050.
    narrator?: string
  },
): Promise<PaginatedResponse<Hadith>> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (filters?.collection) params.set('collection', filters.collection)
  if (filters?.source_corpus) params.set('source_corpus', filters.source_corpus)
  if (filters?.grade) params.set('grade', filters.grade)
  if (filters?.q) params.set('q', filters.q)
  if (filters?.narrator) params.set('narrator', filters.narrator)
  return fetchJson(`${API_BASE}/hadiths?${params}`)
}

export async function fetchHadith(id: string): Promise<Hadith> {
  return fetchJson(`${API_BASE}/hadiths/${encodeURIComponent(id)}`)
}

export async function fetchHadithFacets(): Promise<HadithFacetsResponse> {
  return fetchJson(`${API_BASE}/hadiths/facets`)
}

export async function fetchHadithParallels(id: string): Promise<ParallelsResponse> {
  return fetchJson(`${API_BASE}/parallels/${encodeURIComponent(id)}`)
}

export async function fetchParallelPairs(
  page = 1,
  limit = 20,
  crossSect?: boolean,
): Promise<ParallelPairsResponse> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (crossSect !== undefined) {
    params.set('cross_sect', String(crossSect))
  }
  return fetchJson(`${API_BASE}/parallels?${params.toString()}`)
}

export async function fetchCollections(
  page = 1,
  limit = 20,
): Promise<PaginatedResponse<Collection>> {
  return fetchJson(`${API_BASE}/collections?page=${page}&limit=${limit}`)
}

export async function fetchCollection(id: string): Promise<Collection> {
  return fetchJson(`${API_BASE}/collections/${encodeURIComponent(id)}`)
}

export async function fetchTimelineRange(): Promise<TimelineRangeResponse> {
  return fetchJson(`${API_BASE}/timeline/range`)
}

export async function fetchTimeline(
  startYear?: number,
  endYear?: number,
): Promise<TimelineResponse> {
  const params = new URLSearchParams()
  if (startYear != null) params.set('start_year', String(startYear))
  if (endYear != null) params.set('end_year', String(endYear))
  const qs = params.toString()
  return fetchJson(`${API_BASE}/timeline${qs ? `?${qs}` : ''}`)
}

export async function fetchGraphNetwork(
  narratorId: string,
  depth = 1,
): Promise<NarratorNetworkResponse> {
  const params = new URLSearchParams({
    depth: String(depth),
  })
  return fetchJson(
    `${API_BASE}/graph/narrator/${encodeURIComponent(narratorId)}/network?${params}`,
  )
}

// Per-request batch size the search page fetches for each endpoint. These are the
// server-side page sizes threaded to ``searchAll``/``searchSemantic`` as ``limit``
// and MUST stay within the ``limit`` ``le=`` bounds in ``src/api/routes/search.py``
// (both le=100) — requesting more triggers a 422 (#1025). Server-side pagination
// (``page``) lets the results page fetch subsequent batches, so these are a batch
// window, no longer a hard result ceiling (ig#1147).
export const SEARCH_MAX_LIMIT = 100
export const SEMANTIC_SEARCH_MAX_LIMIT = 50

export async function searchAll(
  query: string,
  limit = 20,
  page = 1,
): Promise<SearchResultsResponse> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
    page: String(page),
  })
  return fetchJson(`${API_BASE}/search?${params}`)
}

export async function searchSemantic(
  query: string,
  limit = 10,
  page = 1,
): Promise<SearchResultsResponse> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
    page: String(page),
  })
  return fetchJson(`${API_BASE}/search/semantic?${params}`)
}

// --- Admin: Moderation ---

export async function fetchModerationItems(
  page = 1,
  limit = 20,
  status?: string,
): Promise<PaginatedResponse<ModerationItem>> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (status) params.set('status', status)
  return fetchJson(`${API_BASE}/admin/moderation?${params}`)
}

export async function updateModerationItem(
  id: string,
  status: string,
  notes?: string,
): Promise<ModerationItem> {
  const body: Record<string, string> = { status }
  if (notes) body.notes = notes
  const res = await fetch(`${API_BASE}/admin/moderation/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw apiError(res)
  return res.json() as Promise<ModerationItem>
}

export async function flagContent(
  entityType: string,
  entityId: string,
  reason: string,
): Promise<ModerationItem> {
  const res = await fetch(`${API_BASE}/admin/moderation/flag`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({ entity_type: entityType, entity_id: entityId, reason }),
  })
  if (!res.ok) throw apiError(res)
  return res.json() as Promise<ModerationItem>
}

// --- Subscription ---

// 404 from /subscriptions/me is a terminal "no subscription" data state
// (free tier / admin), not an error. Resolve it to null and let callers
// branch on `subscription === null`. Other non-OK statuses throw as usual.
export async function fetchSubscriptionOrNull(): Promise<SubscriptionResponse | null> {
  let res = await fetch(`${SUBSCRIPTIONS_BASE}/me`, {
    headers: getAuthHeaders(),
    credentials: 'include',
  })
  // Same refresh-then-retry-once recovery as fetchJson: a mid-session access
  // token expiry must not force a logout while the refresh cookie is still
  // valid. (#1016)
  if (res.status === 401) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      res = await fetch(`${SUBSCRIPTIONS_BASE}/me`, {
        headers: getAuthHeaders(),
        credentials: 'include',
      })
    }
    if (res.status === 401) {
      emitSessionExpired()
    }
  }
  if (res.status === 404) return null
  if (!res.ok) {
    throw apiError(res)
  }
  return res.json() as Promise<SubscriptionResponse>
}

// --- Admin: Reports ---

export async function fetchSystemReports(): Promise<SystemReport> {
  return fetchJson(`${API_BASE}/admin/reports`)
}
