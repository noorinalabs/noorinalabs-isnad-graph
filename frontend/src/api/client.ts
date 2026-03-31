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

const API_BASE = '/api/v1'

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: getAuthHeaders() })
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
  filters?: {
    collection?: string
    source_corpus?: string
    grade?: string
    q?: string
  },
): Promise<PaginatedResponse<Hadith>> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (filters?.collection) params.set('collection', filters.collection)
  if (filters?.source_corpus) params.set('source_corpus', filters.source_corpus)
  if (filters?.grade) params.set('grade', filters.grade)
  if (filters?.q) params.set('q', filters.q)
  return fetchJson(`${API_BASE}/hadiths?${params}`)
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
  const res = await fetch(`${API_BASE}/admin/moderation/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`)
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
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`)
  return res.json() as Promise<ModerationItem>
}

// --- Admin: Reports ---

export async function fetchSystemReports(): Promise<SystemReport> {
  return fetchJson(`${API_BASE}/admin/reports`)
}
