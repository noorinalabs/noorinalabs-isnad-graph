import type {
  AdminUser,
  UserUpdateRequest,
  SystemHealth,
  ContentStats,
  UsageAnalytics,
} from '../types/admin'
import type { PaginatedResponse } from '../types/api'

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
  if (res.status === 401 || res.status === 403) {
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
