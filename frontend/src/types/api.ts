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

export interface Chain {
  id: string
  hadith_id: string
  is_complete: boolean
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

export interface TimelineRangeResponse {
  min_year_ah: number
  max_year_ah: number
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

export interface ParallelPair {
  hadith_a_id: string
  hadith_a_corpus: string
  hadith_b_id: string
  hadith_b_corpus: string
  similarity_score: number | null
  variant_type: string | null
  cross_sect: boolean
}

export interface ParallelPairsResponse {
  items: ParallelPair[]
  total: number
  page: number
  limit: number
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

// --- Moderation types ---

export interface ModerationItem {
  id: string
  entity_type: string
  entity_id: string
  reason: string
  status: string
  flagged_by: string | null
  flagged_at: string
  resolved_by: string | null
  resolved_at: string | null
  notes: string | null
}

// --- System report types ---

export interface PipelineMetrics {
  total_files: number
  total_rows: number
  files: Record<string, unknown>[]
}

export interface DisambiguationMetrics {
  ner_mention_count: number
  canonical_narrator_count: number
  ambiguous_count: number
  resolution_rate_pct: number
  ambiguous_pct: number
}

export interface DedupMetrics {
  parallel_links_count: number
  parallel_verbatim: number
  parallel_close_paraphrase: number
  parallel_thematic: number
  parallel_cross_sect: number
}

export interface GraphValidationMetrics {
  orphan_narrators: number
  orphan_hadiths: number
  chain_integrity_pct: number
  collection_coverage_pct: number
}

export interface TopicCoverageMetrics {
  total_hadiths: number
  classified_count: number
  coverage_pct: number
}

export interface SystemReport {
  pipeline: PipelineMetrics | null
  disambiguation: DisambiguationMetrics | null
  dedup: DedupMetrics | null
  graph_validation: GraphValidationMetrics | null
  topic_coverage: TopicCoverageMetrics | null
}
