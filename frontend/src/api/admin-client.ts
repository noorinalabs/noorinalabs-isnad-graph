import type { components } from '../types/user-service'
import type {
  SystemHealth,
  ContentStats,
  UsageAnalytics,
  DataOverview,
  DataSources,
  PurgeRequest,
  PurgeResult,
  ResetResponse,
  ResetStage,
  FullResetRequest,
} from '../types/admin'
import type { PaginatedResponse } from '../types/api'
import { emitSessionExpired } from '../hooks/useAuth'
import { getAuthHeaders } from './auth-headers'
import { refreshAccessToken } from './token-refresh'
import { apiError } from './api-error'

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

// Issue an authenticated request; on a 401 attempt ONE shared token refresh
// (POST /auth/token/refresh via the httpOnly refresh cookie) and retry the
// request once before the caller surfaces session-expired. Only a genuinely
// expired/revoked refresh cookie (a failed refresh) leaves the response at 401
// for the caller's session-expired branch — a mid-session access-token expiry
// no longer bounces an admin to the login wall. getAuthHeaders() re-reads the
// freshly persisted token on the retry. Mirrors client.ts `fetchJson` (#1016);
// shared by every admin 401 path so the recovery never diverges (#1021).
async function fetchWithRefresh(url: string, init?: RequestInit): Promise<Response> {
  const send = () =>
    fetch(url, { ...init, headers: { ...getAuthHeaders(), ...init?.headers } })
  let res = await send()
  if (res.status === 401) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      res = await send()
    }
  }
  return res
}

async function fetchAdminJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetchWithRefresh(url, { ...init, credentials: 'include' })
  if (res.status === 401) {
    emitSessionExpired()
    throw new Error('Unauthorized: admin access required')
  }
  if (res.status === 403) {
    throw new Error('Unauthorized: admin access required')
  }
  if (!res.ok) {
    throw apiError(res)
  }
  return res.json() as Promise<T>
}

// user-service calls authorize purely via the admin Bearer JWT (no cookies), so
// — unlike the same-origin isnad-graph admin API — they do NOT set
// `credentials: 'include'` (matches profile-client.ts, avoids a cross-origin
// credentialed-CORS requirement on the user-service vhost).
async function fetchUserServiceJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetchWithRefresh(url, init)
  if (res.status === 401) {
    emitSessionExpired()
    throw new Error('Unauthorized: admin access required')
  }
  if (res.status === 403) {
    throw new Error('Unauthorized: admin access required')
  }
  if (!res.ok) {
    throw apiError(res)
  }
  return res.json() as Promise<T>
}

// 204 No Content variant (role removal, soft-delete) — same auth/error handling
// as fetchUserServiceJson but no body to parse.
async function sendUserServiceRequest(url: string, init: RequestInit): Promise<void> {
  const res = await fetchWithRefresh(url, init)
  if (res.status === 401) {
    emitSessionExpired()
    throw new Error('Unauthorized: admin access required')
  }
  if (res.status === 403) {
    throw new Error('Unauthorized: admin access required')
  }
  if (!res.ok) {
    throw apiError(res)
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

// Real user counts are owned by the user-service (the JWT issuer / RBAC
// service); isnad-graph holds no user table. Sourced from the user-service
// admin stats endpoint (ig#1051) — the isnad-graph `/admin/dashboard/stats`
// stub it replaced always reported zeros. `deactivated_users` reflects
// soft-deleted accounts (the service has no separate "suspended" state).
export interface DashboardStats {
  total_users: number
  active_users: number
  deactivated_users: number
  new_registrations_7d: number
  active_sessions: number
  users_by_role: RoleCount[]
}

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const stats = await fetchUserServiceJson<components['schemas']['UserStats']>(
    `${US_USERS_BASE}/stats`,
  )
  return {
    total_users: stats.total_users,
    active_users: stats.active_users,
    deactivated_users: stats.deactivated_users,
    new_registrations_7d: stats.new_registrations_7d,
    active_sessions: stats.active_sessions,
    users_by_role: stats.by_role.map((r) => ({ role: r.role, count: r.count })),
  }
}

// --- Data management (read-only) ---

export async function fetchDataOverview(): Promise<DataOverview> {
  return fetchAdminJson(`${API_BASE}/data/overview`)
}

export async function fetchDataSources(): Promise<DataSources> {
  return fetchAdminJson(`${API_BASE}/data/sources`)
}

// --- Per-source graph purge (ig#989, destructive) ---
// Hits isnad-graph's OWN admin API (same-origin, cookie-credentialed) — unlike
// the pipeline reset below, this is a graph-level DETACH DELETE. Two-phase:
//   * dryRun=true  → preview counts, touches nothing.
//   * dryRun=false → requires `confirmation === sourceCorpus`; the backend
//     rejects a mismatch with 400 (mirrors the OBLITERATE typed-confirm gate).
// The confirmation token only travels on the real run.
export async function purgeSource(
  sourceCorpus: string,
  dryRun: boolean,
  confirmation?: string,
): Promise<PurgeResult> {
  const body: PurgeRequest = { source_corpus: sourceCorpus, dry_run: dryRun }
  if (!dryRun && confirmation !== undefined) {
    body.confirmation = confirmation
  }
  return fetchAdminJson(`${API_BASE}/data/purge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

// ============================================================================
// Pipeline reset — CROSS-SERVICE to ingest-platform (ingest#73, ig#970)
// ----------------------------------------------------------------------------
// These do NOT hit isnad-graph's /api/v1/admin. The reset surface lives on the
// ingest-platform origin and is guarded by the SAME admin Bearer JWT
// (RS256/JWKS). The origin is resolved at module-load time the same
// runtime-over-build-time way as the user-service origin (see useAuth.ts /
// runtime-config.d.ts): window.RUNTIME_CONFIG wins (entrypoint-injected per
// env), then the build-time VITE value (local dev), then same-origin ''.
// NEVER hardcode the origin — a baked URL can't target stg and prod from one
// image digest (Contract v6, #815).
const INGEST_PLATFORM_ORIGIN =
  (typeof window !== 'undefined' && window.RUNTIME_CONFIG?.INGEST_PLATFORM_ORIGIN) ||
  import.meta.env.VITE_INGEST_PLATFORM_ORIGIN ||
  ''
const RESET_BASE = `${INGEST_PLATFORM_ORIGIN}/admin/reset`

// Carries the HTTP status so the UI can branch on it (400 vs 422 vs 503 …)
// instead of string-matching a message.
export class ResetError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ResetError'
    this.status = status
  }
}

async function postReset(path: string, body: unknown): Promise<ResetResponse> {
  const res = await fetchWithRefresh(`${RESET_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (res.ok) {
    return res.json() as Promise<ResetResponse>
  }
  // Pull a server-provided detail if there is one; tolerate a non-JSON body.
  let detail = ''
  try {
    const parsed = (await res.json()) as { detail?: string }
    detail = parsed?.detail ?? ''
  } catch {
    // non-JSON error body (e.g. a proxy 503 HTML page) — fall back to status text
  }
  switch (res.status) {
    case 400:
      // The /full guard: missing or non-"OBLITERATE" confirmation.
      throw new ResetError(400, detail || 'Reset rejected: confirmation missing or incorrect.')
    case 401:
      emitSessionExpired()
      throw new ResetError(401, 'Unauthorized: admin sign-in required.')
    case 403:
      throw new ResetError(403, 'Forbidden: this action requires an admin account.')
    case 422:
      throw new ResetError(422, detail || 'Validation error: check the stage or source value.')
    case 503:
      throw new ResetError(
        503,
        'Service unavailable: the auth key service (JWKS) is unreachable. Try again shortly.',
      )
    default:
      throw new ResetError(res.status, detail || `Reset failed: ${res.status} ${res.statusText}`)
  }
}

export async function resetStage(
  stage: ResetStage,
  dryRun: boolean,
): Promise<ResetResponse> {
  return postReset('/stage', { stage, dry_run: dryRun })
}

export async function resetSource(
  source: string,
  dryRun: boolean,
): Promise<ResetResponse> {
  return postReset('/source', { source, dry_run: dryRun })
}

export async function resetFull(
  confirmation: string,
  dryRun: boolean,
): Promise<ResetResponse> {
  // ingest#73 requires `confirmation:"OBLITERATE"` on BOTH dry-run and real
  // run (REQUIRED field, extra="forbid" → a token-less body 422s before the
  // handler runs). Callers pass the token on both; we omit it only when an
  // empty string is given, which deliberately reproduces the rejected
  // token-less shape so the fetch-boundary regression test can assert the 422.
  const body: FullResetRequest = { dry_run: dryRun }
  if (confirmation) {
    body.confirmation = confirmation
  }
  return postReset('/full', body)
}
