import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"

import {
  fetchAdminUsers,
  updateAdminUser,
  fetchSystemHealth,
  fetchDashboardStats,
  bulkUserAction,
  getUsersExportUrl,
} from "../admin-client"

// admin-client funnels every request through `fetchAdminJson`, which has
// distinct branches for 401 (emit + throw), 403 (throw, no emit), other
// non-OK (throw), plus auth-header injection and `credentials: include`.
// We mock the session-expired emitter and `fetch` to cover each branch.
vi.mock("../../hooks/useAuth", () => ({
  emitSessionExpired: vi.fn(),
}))

import { emitSessionExpired } from "../../hooks/useAuth"

const mockEmit = emitSessionExpired as ReturnType<typeof vi.fn>

function jsonResponse(status: number, body: unknown = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

describe("admin-client — fetchAdminJson behavior", () => {
  beforeEach(() => {
    mockEmit.mockReset()
    localStorage.clear()
    vi.spyOn(globalThis, "fetch")
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("returns the parsed body on 200", async () => {
    const payload = { items: [], total: 0, page: 1, limit: 20 }
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(200, payload))

    await expect(fetchAdminUsers()).resolves.toEqual(payload)
    expect(mockEmit).not.toHaveBeenCalled()
  })

  it("attaches the bearer token and credentials:include on every request", async () => {
    localStorage.setItem("access_token", "admin-token")
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(200, { active_sessions: 3 }))

    await fetchDashboardStats()

    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0]!
    expect((init as RequestInit).credentials).toBe("include")
    expect((init as RequestInit).headers).toMatchObject({
      Authorization: "Bearer admin-token",
    })
  })

  it("omits the Authorization header when no token is stored", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(200, {}))

    await fetchSystemHealth()

    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0]!
    expect((init as RequestInit).headers).not.toHaveProperty("Authorization")
  })

  it("emits sessionExpired and throws on 401", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(401, { detail: "unauthorized" }))

    await expect(fetchAdminUsers()).rejects.toThrow(/admin access required/)
    expect(mockEmit).toHaveBeenCalledTimes(1)
  })

  it("throws on 403 WITHOUT emitting sessionExpired (forbidden != expired)", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(403, { detail: "forbidden" }))

    await expect(fetchSystemHealth()).rejects.toThrow(/admin access required/)
    // 403 means "you're authed but not allowed" — re-auth wouldn't help, so
    // the session-expired modal must NOT fire.
    expect(mockEmit).not.toHaveBeenCalled()
  })

  it("throws a status-bearing error on other non-OK responses (500)", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(500, { detail: "boom" }))

    await expect(fetchDashboardStats()).rejects.toThrow(/500/)
    expect(mockEmit).not.toHaveBeenCalled()
  })

  it("forwards method, JSON body, and merges Content-Type with auth headers on mutations", async () => {
    localStorage.setItem("access_token", "admin-token")
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(200, { id: "u1" }))

    await updateAdminUser("u1", { is_suspended: true })

    const [url, init] = vi.mocked(globalThis.fetch).mock.calls[0]!
    expect(url).toContain("/api/v1/admin/users/u1")
    const ri = init as RequestInit
    expect(ri.method).toBe("PATCH")
    expect(ri.body).toBe(JSON.stringify({ is_suspended: true }))
    expect(ri.headers).toMatchObject({
      "Content-Type": "application/json",
      Authorization: "Bearer admin-token",
    })
  })

  it("encodes path params to guard against id-injection in the URL", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(200, { id: "weird id" }))

    await updateAdminUser("weird id/../x", { is_suspended: false })

    const [url] = vi.mocked(globalThis.fetch).mock.calls[0]!
    expect(url).toContain(encodeURIComponent("weird id/../x"))
    expect(url).not.toContain("weird id/../x")
  })

  it("sends a POST with the user-id list for bulk actions", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      jsonResponse(200, { affected: 2, action: "suspend" }),
    )

    const res = await bulkUserAction(["a", "b"], "suspend")

    expect(res).toEqual({ affected: 2, action: "suspend" })
    const [url, init] = vi.mocked(globalThis.fetch).mock.calls[0]!
    expect(url).toContain("/api/v1/admin/users/bulk")
    expect((init as RequestInit).method).toBe("POST")
    expect((init as RequestInit).body).toBe(
      JSON.stringify({ user_ids: ["a", "b"], action: "suspend", role: undefined }),
    )
  })
})

describe("admin-client — getUsersExportUrl (pure URL builder)", () => {
  it("returns the bare export path when no filters are given", () => {
    expect(getUsersExportUrl()).toBe("/api/v1/admin/users/export/csv")
  })

  it("appends search and role as query params when provided", () => {
    const url = getUsersExportUrl("jane", "admin")
    expect(url).toContain("/api/v1/admin/users/export/csv?")
    expect(url).toContain("search=jane")
    expect(url).toContain("role=admin")
  })

  it("omits empty filters from the query string", () => {
    const url = getUsersExportUrl(undefined, "editor")
    expect(url).toContain("role=editor")
    expect(url).not.toContain("search=")
  })
})
