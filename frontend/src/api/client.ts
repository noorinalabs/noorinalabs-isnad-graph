import type {
  PaginatedResponse,
  Narrator,
  Hadith,
  Collection,
  NarratorChainsResponse,
  SearchResultsResponse,
  TimelineResponse,
  TimelineRangeResponse,
  ParallelsResponse,
  ParallelPairsResponse,
  NarratorNetworkResponse,
  ModerationItem,
  SystemReport,
} from '../types/api'

import { API_BASE } from '../config'

// Promise-based mutex: only one refresh request at a time.
// Concurrent 401 handlers await the existing promise instead of firing new requests.
let refreshPromise: Promise<boolean> | null = null

async function attemptTokenRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    })
    return res.ok
  } catch {
    return false
  }
}

function refreshOnce(): Promise<boolean> {
  if (refreshPromise) {
    return refreshPromise
  }
  refreshPromise = attemptTokenRefresh().finally(() => {
    refreshPromise = null
  })
  return refreshPromise
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    credentials: 'include',
    headers: { ...init?.headers },
  })

  if (res.status === 401) {
    const refreshed = await refreshOnce()
    if (refreshed) {
      // Notify useAuth to re-fetch user state after token refresh
      const refreshFn = (window as unknown as Record<string, unknown>).__refreshAuthState
      if (typeof refreshFn === 'function') {
        ;(refreshFn as () => Promise<void>)()
      }
      const retry = await fetch(url, {
        ...init,
        credentials: 'include',
        headers: { ...init?.headers },
      })
      if (retry.ok) {
        return retry.json() as Promise<T>
      }
    }
    // Refresh failed or retry still 401 — redirect to login
    window.location.href = '/login'
    throw new Error('Authentication expired')
  }

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
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

export async function fetchHadiths(
  page = 1,
  limit = 20,
): Promise<PaginatedResponse<Hadith>> {
  return fetchJson(`${API_BASE}/hadiths?page=${page}&limit=${limit}`)
}

export async function fetchHadith(id: string): Promise<Hadith> {
  return fetchJson(`${API_BASE}/hadiths/${encodeURIComponent(id)}`)
}

export async function fetchHadithParallels(id: string): Promise<ParallelsResponse> {
  return fetchJson(`${API_BASE}/parallels/${encodeURIComponent(id)}`)
}

export async function fetchParallelPairs(
  page = 1,
  limit = 20,
): Promise<ParallelPairsResponse> {
  return fetchJson(`${API_BASE}/parallels?page=${page}&limit=${limit}`)
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

export async function searchAll(
  query: string,
  limit = 20,
): Promise<SearchResultsResponse> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
  })
  return fetchJson(`${API_BASE}/search?${params}`)
}

export async function searchSemantic(
  query: string,
  limit = 10,
): Promise<SearchResultsResponse> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
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
  return fetchJson(`${API_BASE}/admin/moderation/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function flagContent(
  entityType: string,
  entityId: string,
  reason: string,
): Promise<ModerationItem> {
  return fetchJson(`${API_BASE}/admin/moderation/flag`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ entity_type: entityType, entity_id: entityId, reason }),
  })
}

// --- Admin: Reports ---

export async function fetchSystemReports(): Promise<SystemReport> {
  return fetchJson(`${API_BASE}/admin/reports`)
}
