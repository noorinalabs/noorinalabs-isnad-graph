export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
}

export interface Narrator {
  id: string
  name_ar: string
  // name_en/generation/gender/sect_affiliation/trustworthiness_consensus are
  // nullable to match the API's NarratorResponse contract (#1024/#1046): the
  // graph carries these only for a subset of narrators. Render paths null-guard.
  name_en: string | null
  kunya: string | null
  nisba: string | null
  laqab: string | null
  birth_year_ah: number | null
  death_year_ah: number | null
  generation: string | null
  gender: string | null
  sect_affiliation: string | null
  trustworthiness_consensus: string | null
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
  grade_normalized: string | null
  topic_tags: string[]
  source_corpus: string
  collection_name: string | null
  display_title: string | null
  has_shia_parallel: boolean
  has_sunni_parallel: boolean
}

export interface TopicFacet {
  /** Canonical topic token, or "uncategorized". */
  value: string
  label: string
  count: number
}

export interface HadithFacetsResponse {
  source_corpus: string[]
  grades: string[]
  /** Canonical topic vocabulary with per-bucket counts (incl. uncategorized). */
  topics: TopicFacet[]
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
  // Facet metadata, populated per result type (see backend SearchResult).
  // `grade` is the canonical normalized token (e.g. "sahih", "daif"), not raw
  // scholar text. Absent/empty where the attribute does not apply. (#1036)
  collection?: string | null
  grade?: string | null
  century?: number | null
  topics?: string[]
}

export interface SearchResultsResponse {
  results: SearchResult[]
  total: number
  query: string
  // 1-based page this response corresponds to. Defaulted to 1 for older backends
  // that omit it, so pagination math stays safe pre-deploy. (ig#1147)
  page?: number
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

export interface NarratorTimelineEntry {
  narrator_id: string
  name_ar: string | null
  name_en: string | null
  birth_year_ah: number | null
  death_year_ah: number | null
  window_start_ah: number
  window_end_ah: number
  birth_date_precision: string | null
  death_date_precision: string | null
  tabaqat_class: string | null
  estimated: boolean
}

export interface NarratorTimelineResponse {
  entries: NarratorTimelineEntry[]
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

export interface ParallelPair {
  hadith_a_id: string
  hadith_a_corpus: string
  // Human-readable title + short matn preview for readable Browse rows (#1037).
  hadith_a_title?: string | null
  hadith_a_snippet?: string | null
  hadith_b_id: string
  hadith_b_corpus: string
  hadith_b_title?: string | null
  hadith_b_snippet?: string | null
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
  community_id: number | null
  in_degree: number | null
  out_degree: number | null
  betweenness_centrality: number | null
  pagerank: number | null
  sect_affiliation: string | null
  trustworthiness_consensus: string | null
  death_year_ah: number | null
  birth_year_ah: number | null
  kunya: string | null
  nisba: string | null
}

export interface GraphEdge {
  source: string
  target: string
  relationship: string
  weight: number
  // Ordinal position within a single hadith's isnad chain (TRANSMITTED_TO
  // position_in_chain). Only set by the per-hadith chain endpoint.
  position?: number | null
}

export interface ChainVisualization {
  hadith_id: string
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface NarratorNetworkResponse {
  narrator_id: string
  nodes: GraphNode[]
  edges: GraphEdge[]
  teachers: number
  students: number
}

// A narrator's resolved [start, end] active window in Hijri years. `estimated`
// is true when either endpoint was derived from an assumed-lifespan span.
export interface NarratorWindow {
  narrator_id: string
  name_ar?: string | null
  name_en?: string | null
  birth_year_ah?: number | null
  death_year_ah?: number | null
  window_start_ah?: number | null
  window_end_ah?: number | null
  estimated: boolean
}

// Chain-derived dating window for a hadith (ig#1042). Termini are anchored on
// the earliest/latest narrator death across the isnad chain. When no chain
// narrator is dated, all three bounds are null and `confidence` is
// `insufficient_data` (with a human-readable `note`).
export interface HadithDatingResponse {
  hadith_id: string
  terminus_post_quem_ah: number | null
  terminus_ante_quem_ah: number | null
  chain_span_ah: number | null
  confidence: 'high' | 'medium' | 'low' | 'insufficient_data'
  chain_narrator_count: number
  dated_narrator_count: number
  earliest_narrator: NarratorWindow | null
  latest_narrator: NarratorWindow | null
  assumed_lifespan_ah: number
  note: string
}

// --- Subscription types ---

export type SubscriptionTier = 'trial' | 'individual' | 'team' | 'enterprise'
export type SubscriptionStatus = 'trial' | 'active' | 'expired' | 'cancelled'

export interface SubscriptionResponse {
  tier: SubscriptionTier
  status: SubscriptionStatus
  days_remaining: number
  trial_start: string | null
  trial_expires: string | null
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
