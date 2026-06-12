import type { components } from '../types/user-service'
import type { SystemHealth, ContentStats, UsageAnalytics } from '../types/admin'
import type { PaginatedResponse } from '../types/api'
import { emitSessionExpired } from '../hooks/useAuth'
import { getAuthHeaders } from './auth-headers'

// --- isnad-graph admin API (system / content / analytics panels — #806) ---
const API_BASE = '/api/v1/admin'

// --- user-service admin API (user + role management — #805) ---
// User CRUD and roles live in the user-service (the JWT issuer / RBAC service);
// the isnad-graph `/api/v1/admin/users` routes are now 501 stubs. These calls
// target the user-service vhost (`users.{base}`) directly with the same admin
// Bearer JWT. The origin is resolved at runtime from `window.RUNTIME_CONFIG`
// (injected by the container entrypoint via /runtime-config.js) so a single
// image digest serves env-specific origins; it falls back to the build-time
// `VITE_USER_SERVICE_ORIGIN` for local `npm run dev`, then '' (same-origin).
// Mirrors the resolution in useAuth.ts / profile-client.ts (isnad-graph#932).
const USER_SERVICE_ORIGIN =
  (typeof window !== 'undefined' && window.RUNTIME_CONFIG?.USER_SERVICE_ORIGIN) ||
  import.meta.env.VITE_USER_SERVICE_ORIGIN ||
  ''
const US_USERS_BASE = `${USER_SERVICE_ORIGIN}/api/v1/users`
const US_ROLES_BASE = `${USER_SERVICE_ORIGIN}/api/v1/roles`

// Canonical user/role shapes are sourced from the committed user-service
// OpenAPI snapshot (`frontend/src/types/user-service.d.ts`); drift is enforced
// by the `frontend-typegen-drift` CI job, the same as in useAuth.ts.
export type AdminUser = components['schemas']['UserRead']
export type AdminUserList = components['schemas']['UserListResponse']
export type Role = components['schemas']['RoleRead']

async function fetchAdminJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    credentials: 'include',
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

// user-service calls authorize purely via the admin Bearer JWT (no cookies), so
// — unlike the same-origin isnad-graph admin API — they do NOT set
// `credentials: 'include'` (matches profile-client.ts, avoids a cross-origin
// credentialed-CORS requirement on the user-service vhost).
async function fetchUserServiceJson<T>(url: string, init?: RequestInit): Promise<T> {
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

// 204 No Content variant (role removal, soft-delete) — same auth/error handling
// as fetchUserServiceJson but no body to parse.
async function sendUserServiceRequest(url: string, init: RequestInit): Promise<void> {
  const res = await fetch(url, {
    ...init,
    headers: { ...getAuthHeaders(), ...init.headers },
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
}

// List users (admin). The user-service paginates by opaque cursor, NOT page
// number — pass the previous response's `next_cursor` to advance.
export async function fetchAdminUsers(
  cursor?: string | null,
  limit = 20,
): Promise<AdminUserList> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (cursor) params.set('cursor', cursor)
  return fetchUserServiceJson(`${US_USERS_BASE}?${params}`)
}

export async function fetchAdminUser(userId: string): Promise<AdminUser> {
  return fetchUserServiceJson(`${US_USERS_BASE}/${encodeURIComponent(userId)}`)
}

// Role catalog (name → id). Any authenticated user may read it; the admin panel
// needs it to translate a role *name* (what the UI shows) into the role *id*
// (uuid) the assign/remove endpoints require.
export async function fetchRoles(): Promise<Role[]> {
  return fetchUserServiceJson(US_ROLES_BASE)
}

export async function assignUserRole(userId: string, roleId: string): Promise<Role> {
  return fetchUserServiceJson(`${US_USERS_BASE}/${encodeURIComponent(userId)}/roles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role_id: roleId }),
  })
}

export async function removeUserRole(userId: string, roleId: string): Promise<void> {
  return sendUserServiceRequest(
    `${US_USERS_BASE}/${encodeURIComponent(userId)}/roles/${encodeURIComponent(roleId)}`,
    { method: 'DELETE' },
  )
}

// Soft-delete (deactivate) a user. The user-service has no reactivate endpoint,
// so this is one-way — callers should confirm before invoking.
export async function deactivateUser(userId: string): Promise<void> {
  return sendUserServiceRequest(`${US_USERS_BASE}/${encodeURIComponent(userId)}`, {
    method: 'DELETE',
  })
}

// Switch a user to exactly one role. The user-service models roles as an
// additive set (assign / remove by role_id) rather than a single mutable field,
// so "set role" = assign the target (if absent) then remove every *other*
// catalog role the user currently holds. `catalog` is {@link fetchRoles}'s
// output (name → id); `currentRoleNames` is the user's present `roles`.
export async function setUserRole(
  userId: string,
  targetRoleName: string,
  currentRoleNames: string[],
  catalog: Role[],
): Promise<void> {
  const target = catalog.find((r) => r.name === targetRoleName)
  if (!target) {
    throw new Error(`Unknown role: ${targetRoleName}`)
  }
  if (!currentRoleNames.includes(targetRoleName)) {
    await assignUserRole(userId, target.id)
  }
  for (const role of catalog) {
    if (role.name !== targetRoleName && currentRoleNames.includes(role.name)) {
      await removeUserRole(userId, role.id)
    }
  }
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
  total_users?: number
  active_users?: number
  suspended_users?: number
  users_by_role?: RoleCount[]
  new_registrations_7d?: number
  active_sessions: number
}

export async function fetchDashboardStats(): Promise<DashboardStats> {
  return fetchAdminJson(`${API_BASE}/dashboard/stats`)
}

