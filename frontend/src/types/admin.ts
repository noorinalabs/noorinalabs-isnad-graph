export interface AdminUser {
  id: string
  email: string
  name: string
  provider: string
  is_admin: boolean
  is_suspended: boolean
  created_at: string
  role: string | null
}

export interface UserUpdateRequest {
  is_admin?: boolean
  is_suspended?: boolean
  role?: string
}

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
