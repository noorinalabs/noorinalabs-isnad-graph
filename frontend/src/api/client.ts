import type {
  PaginatedResponse,
  Narrator,
  Hadith,
  Collection,
  NarratorChainsResponse,
  SearchResultsResponse,
  TimelineResponse,
  ParallelsResponse,
  NarratorNetworkResponse,
} from '../types/api'

const API_BASE = '/api/v1'

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
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

export async function fetchCollections(): Promise<Collection[]> {
  return fetchJson(`${API_BASE}/collections`)
}

export async function fetchCollection(id: string): Promise<Collection> {
  return fetchJson(`${API_BASE}/collections/${encodeURIComponent(id)}`)
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
