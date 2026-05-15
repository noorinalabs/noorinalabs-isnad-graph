import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"

import {
  fetchProfile,
  updateProfile,
  fetchSessions,
  revokeSession,
} from "../profile-client"

// profile-client has two non-OK guards: the shared `fetchProfileJson`
// (401 -> emit + throw, other -> throw) and a hand-rolled equivalent inside
// `revokeSession` (which returns void, not JSON). Both must emit on 401.
vi.mock("../../hooks/useAuth", () => ({
  emitSessionExpired: vi.fn(),
}))

import { emitSessionExpired } from "../../hooks/useAuth"

const mockEmit = emitSessionExpired as ReturnType<typeof vi.fn>

function jsonResponse(status: number, body: unknown = {}): Response {
  // 204/304 are null-body statuses — the Response constructor rejects a body
  // for them. Everything else carries the JSON payload.
  const nullBody = status === 204 || status === 304
  return new Response(nullBody ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

const PROFILE = {
  id: "u1",
  email: "jane@example.com",
  display_name: "Jane Smith",
  email_verified: true,
  avatar_url: null,
  locale: null,
  is_active: true,
  created_at: "2026-04-20T00:00:00Z",
  roles: ["viewer"],
}

describe("profile-client — fetchProfileJson behavior", () => {
  beforeEach(() => {
    mockEmit.mockReset()
    localStorage.clear()
    vi.spyOn(globalThis, "fetch")
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("returns the parsed profile on 200", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(200, PROFILE))

    await expect(fetchProfile()).resolves.toEqual(PROFILE)
    expect(mockEmit).not.toHaveBeenCalled()
  })

  it("attaches the bearer token from localStorage", async () => {
    localStorage.setItem("access_token", "profile-token")
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(200, PROFILE))

    await fetchProfile()

    const [url, init] = vi.mocked(globalThis.fetch).mock.calls[0]!
    expect(url).toContain("/api/v1/users/me")
    expect((init as RequestInit).headers).toMatchObject({
      Authorization: "Bearer profile-token",
    })
  })

  it("emits sessionExpired and throws Unauthorized on 401", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(401, { detail: "nope" }))

    await expect(fetchProfile()).rejects.toThrow(/Unauthorized/)
    expect(mockEmit).toHaveBeenCalledTimes(1)
  })

  it("throws a status-bearing error on other non-OK responses without emitting", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(500, { detail: "boom" }))

    await expect(fetchProfile()).rejects.toThrow(/500/)
    expect(mockEmit).not.toHaveBeenCalled()
  })

  it("updateProfile sends a PATCH with the JSON body and merged headers", async () => {
    localStorage.setItem("access_token", "profile-token")
    vi.mocked(globalThis.fetch).mockResolvedValue(
      jsonResponse(200, { ...PROFILE, display_name: "Jane R." }),
    )

    const res = await updateProfile({ display_name: "Jane R." })

    expect(res.display_name).toBe("Jane R.")
    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0]!
    const ri = init as RequestInit
    expect(ri.method).toBe("PATCH")
    expect(ri.body).toBe(JSON.stringify({ display_name: "Jane R." }))
    expect(ri.headers).toMatchObject({
      "Content-Type": "application/json",
      Authorization: "Bearer profile-token",
    })
  })

  it("fetchSessions unwraps the `sessions` array from the list response", async () => {
    const sessions = [
      { id: "s1", is_current: true },
      { id: "s2", is_current: false },
    ]
    vi.mocked(globalThis.fetch).mockResolvedValue(
      jsonResponse(200, { sessions, count: 2 }),
    )

    await expect(fetchSessions()).resolves.toEqual(sessions)
  })
})

describe("profile-client — revokeSession (void return, own non-OK guard)", () => {
  beforeEach(() => {
    mockEmit.mockReset()
    vi.spyOn(globalThis, "fetch")
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("resolves without a value on a successful DELETE", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(204))

    await expect(revokeSession("s1")).resolves.toBeUndefined()
    const [url, init] = vi.mocked(globalThis.fetch).mock.calls[0]!
    expect(url).toContain("/api/v1/sessions/s1")
    expect((init as RequestInit).method).toBe("DELETE")
  })

  it("encodes the session id in the path", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(204))

    await revokeSession("weird/id")

    const [url] = vi.mocked(globalThis.fetch).mock.calls[0]!
    expect(url).toContain(encodeURIComponent("weird/id"))
  })

  it("emits sessionExpired and throws on 401", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(401, { detail: "nope" }))

    await expect(revokeSession("s1")).rejects.toThrow(/Unauthorized/)
    expect(mockEmit).toHaveBeenCalledTimes(1)
  })

  it("throws a status-bearing error on other non-OK responses", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(500))

    await expect(revokeSession("s1")).rejects.toThrow(/500/)
    expect(mockEmit).not.toHaveBeenCalled()
  })
})
