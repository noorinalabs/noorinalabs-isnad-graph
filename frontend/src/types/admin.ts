// User/role shapes for the admin user-management panel are sourced from the
// user-service OpenAPI snapshot (re-exported as `AdminUser` / `Role` from
// `../api/admin-client`) since user CRUD moved to the user-service (#805).
// The types below back the system / content / analytics panels (#806).

export interface SystemHealth {
  status: string
  neo4j: boolean
  postgres: boolean
  redis: boolean
}

export interface ContentStats {
  hadith_count: number
  narrator_count: number
  collection_count: number
  coverage_pct: number
}

export interface PopularNarrator {
  id: string
  name: string
  query_count: number
}

export interface UsageAnalytics {
  search_volume: number
  api_call_count: number
  popular_narrators: PopularNarrator[]
}

export interface NodeCount {
  label: string
  count: number
}

export interface RelationshipCount {
  rel_type: string
  count: number
}

export interface DataOverview {
  node_counts: NodeCount[]
  relationship_counts: RelationshipCount[]
  total_nodes: number
  total_relationships: number
}

export interface SourceBreakdown {
  source_corpus: string
  hadith_count: number
  collection_count: number
}

export interface DataSources {
  sources: SourceBreakdown[]
  total_hadiths: number
  total_collections: number
  distinct_sources: number
}

// --- Pipeline reset (ingest-platform cross-service contract, ingest#73) ---
// The reset endpoints live in the ingest-platform service, NOT isnad-graph's
// /api/v1/admin. These types mirror the wire contract the UI consumes.

// Ordered low→high in the pipeline; mirrors the ingest-platform CLI stages.
export type ResetStage = 'raw' | 'dedup' | 'enriched' | 'normalized' | 'staged'

export type ResetLevel = 'stage' | 'source' | 'full'

// `summary` is intentionally loose: the contract returns a free-form preview
// blob (object or string) describing what would be / was wiped. The UI renders
// it without assuming an inner shape so a contract addition can't break the page.
export type ResetSummary = string | Record<string, unknown>

export interface ResetResponse {
  level: ResetLevel
  dry_run: boolean
  confirmation_method: string
  audit_entry_path: string
  summary: ResetSummary
}

export interface StageResetRequest {
  stage: ResetStage
  dry_run?: boolean
}

export interface SourceResetRequest {
  source: string
  dry_run?: boolean
}

export interface FullResetRequest {
  // Required for the REAL /full run (server rejects 400 unless "OBLITERATE").
  // Omitted on the dry-run preview — the token only ever travels on the real
  // run (defense in depth: the destructive word is never sent speculatively).
  confirmation?: string
  dry_run?: boolean
}
