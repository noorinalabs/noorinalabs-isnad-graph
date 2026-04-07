import type {
  AdminUser,
  UserUpdateRequest,
  SystemHealth,
  ContentStats,
  UsageAnalytics,
} from '../types/admin'
import type { PaginatedResponse } from '../types/api'
import { emitSessionExpired } from '../hooks/useAuth'

const API_BASE = '/api/v1/admin'

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function fetchAdminJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { ...getAuthHeaders(), ...init?.headers },
  })
  if (res.status === 401) {
    emitSessionExpired()
    throw new Error('Unauthorized: admin access required')
  }
  if (res.status === 403) {
    throw new Error('Unauthorized: admin access required')
  }
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export async function fetchAdminUsers(
  page = 1,
  limit = 20,
  search?: string,
  role?: string,
): Promise<PaginatedResponse<AdminUser>> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (search) params.set('search', search)
  if (role) params.set('role', role)
  return fetchAdminJson(`${API_BASE}/users?${params}`)
}

export async function fetchAdminUser(userId: string): Promise<AdminUser> {
  return fetchAdminJson(`${API_BASE}/users/${encodeURIComponent(userId)}`)
}

export async function updateAdminUser(
  userId: string,
  body: UserUpdateRequest,
): Promise<AdminUser> {
  return fetchAdminJson(`${API_BASE}/users/${encodeURIComponent(userId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function fetchSystemHealth(): Promise<SystemHealth> {
  return fetchAdminJson(`${API_BASE}/health/ready`)
}

export async function fetchContentStats(): Promise<ContentStats> {
  return fetchAdminJson(`${API_BASE}/stats`)
}

export async function fetchUsageAnalytics(): Promise<UsageAnalytics> {
  return fetchAdminJson(`${API_BASE}/analytics`)
}

export interface AuditLogEntry {
  id: string
  action: string
  target_user_id: string | null
  actor_id: string
  actor_name: string
  details: string
  created_at: string
}

export async function fetchAuditLogs(
  page = 1,
  limit = 20,
  action?: string,
): Promise<PaginatedResponse<AuditLogEntry>> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (action) params.set('action', action)
  return fetchAdminJson(`${API_BASE}/audit?${params}`)
}

export interface RoleCount {
  role: string
  count: number
}

export interface DashboardStats {
  total_users: number
  active_users: number
  suspended_users: number
  users_by_role: RoleCount[]
  new_registrations_7d: number
  active_sessions: number
}

export async function fetchDashboardStats(): Promise<DashboardStats> {
  return fetchAdminJson(`${API_BASE}/dashboard/stats`)
}

export interface BulkActionResponse {
  affected: number
  action: string
}

export async function bulkUserAction(
  userIds: string[],
  action: string,
  role?: string,
): Promise<BulkActionResponse> {
  return fetchAdminJson(`${API_BASE}/users/bulk`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_ids: userIds, action, role }),
  })
}

export interface UserDetail {
  id: string
  email: string
  name: string
  provider: string
  is_admin: boolean
  is_suspended: boolean
  created_at: string
  role: string | null
  login_count: number
  last_login: string | null
}

export async function fetchUserDetail(userId: string): Promise<UserDetail> {
  return fetchAdminJson(`${API_BASE}/users/${encodeURIComponent(userId)}/detail`)
}

export function getUsersExportUrl(search?: string, role?: string): string {
  const params = new URLSearchParams()
  if (search) params.set('search', search)
  if (role) params.set('role', role)
  const qs = params.toString()
  return `${API_BASE}/users/export/csv${qs ? `?${qs}` : ''}`
}

export async function updateUserRole(
  userId: string,
  role: string,
): Promise<AdminUser> {
  return fetchAdminJson(`${API_BASE}/users/${encodeURIComponent(userId)}/role`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role }),
  })
}
