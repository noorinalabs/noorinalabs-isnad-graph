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
