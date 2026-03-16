export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
}

export interface Narrator {
  id: string
  name_ar: string
  name_en: string
  kunya: string | null
  nisba: string | null
  laqab: string | null
  birth_year_ah: number | null
  death_year_ah: number | null
  generation: string
  gender: string
  sect_affiliation: string
  trustworthiness_consensus: string
  aliases: string[]
  betweenness_centrality: number | null
  in_degree: number | null
  out_degree: number | null
  pagerank: number | null
  community_id: number | null
}

export interface Hadith {
  id: string
  matn_ar: string
  matn_en: string | null
  isnad_raw_ar: string | null
  isnad_raw_en: string | null
  grade_composite: string | null
  topic_tags: string[]
  source_corpus: string
  has_shia_parallel: boolean
  has_sunni_parallel: boolean
}

export interface Collection {
  id: string
  name_ar: string
  name_en: string
  compiler_name: string | null
  compiler_id: string | null
  compilation_year_ah: number | null
  sect: string
  canonical_rank: number | null
  total_hadiths: number | null
  book_count: number | null
}

export interface ChainSummary {
  chain_id: string
  hadith_id: string
  matn_ar: string
  matn_en: string | null
  grade: string | null
}

export interface NarratorChainsResponse {
  narrator_id: string
  chains: ChainSummary[]
  total: number
}

export interface SearchResult {
  id: string
  type: string
  title: string
  title_ar: string
  score: number
}

export interface SearchResultsResponse {
  results: SearchResult[]
  total: number
  query: string
}

export interface TimelineEntry {
  id: string
  name: string
  name_ar: string | null
  year_ah: number
  end_year_ah: number | null
  event_type: string | null
  description: string | null
  narrator_count: number
}

export interface TimelineResponse {
  entries: TimelineEntry[]
  total: number
}

export interface ParallelHadith {
  id: string
  matn_ar: string
  matn_en: string | null
  source_corpus: string
  grade: string | null
  similarity_score: number | null
  variant_type: string | null
  cross_sect: boolean
}

export interface ParallelsResponse {
  hadith_id: string
  parallels: ParallelHadith[]
  total: number
}

export interface GraphNode {
  id: string
  label: string
  name_ar: string
  name_en: string | null
  type: string
  generation: string | null
}

export interface GraphEdge {
  source: string
  target: string
  relationship: string
}

export interface NarratorNetworkResponse {
  narrator_id: string
  nodes: GraphNode[]
  edges: GraphEdge[]
  teachers: number
  students: number
}
