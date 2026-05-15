import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"

import {
  fetchNarrator,
  fetchNarrators,
  searchAll,
  updateModerationItem,
  flagContent,
} from "../client"

// The existing client.test.ts covers fetchSubscriptionOrNull's allowStatuses
// branch. This file covers the rest of `client.ts`: the default (no-opts)
// fetchJson path that always throws on non-OK + emits on 401, the
// auth-header/credentials wiring, query-string construction, and the two
// hand-rolled mutation helpers (updateModerationItem, flagContent) which
// have their own non-OK guards separate from fetchJson.
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

describe("client — fetchJson default path (no allowStatuses)", () => {
  beforeEach(() => {
    mockEmit.mockReset()
    localStorage.clear()
    vi.spyOn(globalThis, "fetch")
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("returns the parsed body on 200", async () => {
    const narrator = { id: "n1", name_ar: "فلان" }
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(200, narrator))

    await expect(fetchNarrator("n1")).resolves.toEqual(narrator)
    expect(mockEmit).not.toHaveBeenCalled()
  })

  it("sends credentials:include and the bearer token when present", async () => {
    localStorage.setItem("access_token", "tok")
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(200, { id: "n1" }))

    await fetchNarrator("n1")

    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0]!
    expect((init as RequestInit).credentials).toBe("include")
    expect((init as RequestInit).headers).toMatchObject({ Authorization: "Bearer tok" })
  })

  it("throws a status-bearing error on 404 (no allowStatuses -> not swallowed)", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(404, { detail: "missing" }))

    await expect(fetchNarrator("nope")).rejects.toThrow(/404/)
    // 404 is not 401 — no session-expired side effect.
    expect(mockEmit).not.toHaveBeenCalled()
  })

  it("emits sessionExpired and throws on 401", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(401, { detail: "expired" }))

    await expect(fetchNarrators()).rejects.toThrow(/401/)
    expect(mockEmit).toHaveBeenCalledTimes(1)
  })

  it("throws on 500", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(500))

    await expect(fetchNarrators()).rejects.toThrow(/500/)
    expect(mockEmit).not.toHaveBeenCalled()
  })

  it("encodes path params (guards against id-injection in the URL)", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(200, { id: "x" }))

    await fetchNarrator("ibn/../malik")

    const [url] = vi.mocked(globalThis.fetch).mock.calls[0]!
    expect(url).toContain(encodeURIComponent("ibn/../malik"))
    expect(url).not.toContain("ibn/../malik")
  })

  it("builds pagination + search query params for list endpoints", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      jsonResponse(200, { items: [], total: 0, page: 2, limit: 5 }),
    )

    await fetchNarrators(2, 5, "malik")

    const [url] = vi.mocked(globalThis.fetch).mock.calls[0]!
    expect(url).toContain("page=2")
    expect(url).toContain("limit=5")
    // Free-text search is passed as `q`.
    expect(url).toContain("q=malik")
  })

  it("omits the search param when no search term is given", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      jsonResponse(200, { items: [], total: 0, page: 1, limit: 20 }),
    )

    await fetchNarrators()

    const [url] = vi.mocked(globalThis.fetch).mock.calls[0]!
    expect(url).not.toContain("q=")
  })

  it("URL-encodes search queries with reserved characters", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(200, { results: [] }))

    await searchAll("ibn & sons")

    const [url] = vi.mocked(globalThis.fetch).mock.calls[0]!
    // URLSearchParams encodes spaces (+) and ampersands (%26) so they don't
    // leak into the query structure.
    expect(url).toContain("q=ibn+%26+sons")
  })
})

describe("client — updateModerationItem (hand-rolled mutation guard)", () => {
  beforeEach(() => {
    mockEmit.mockReset()
    localStorage.clear()
    vi.spyOn(globalThis, "fetch")
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("PATCHes with a JSON body and returns the parsed item on success", async () => {
    localStorage.setItem("access_token", "tok")
    vi.mocked(globalThis.fetch).mockResolvedValue(
      jsonResponse(200, { id: "m1", status: "approved" }),
    )

    const res = await updateModerationItem("m1", "approved", "looks fine")

    expect(res).toEqual({ id: "m1", status: "approved" })
    const [url, init] = vi.mocked(globalThis.fetch).mock.calls[0]!
    expect(url).toContain("/api/v1/admin/moderation/m1")
    const ri = init as RequestInit
    expect(ri.method).toBe("PATCH")
    expect(ri.body).toBe(JSON.stringify({ status: "approved", notes: "looks fine" }))
    expect(ri.headers).toMatchObject({
      "Content-Type": "application/json",
      Authorization: "Bearer tok",
    })
  })

  it("omits notes from the body when not provided", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(200, { id: "m1" }))

    await updateModerationItem("m1", "rejected")

    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0]!
    expect((init as RequestInit).body).toBe(JSON.stringify({ status: "rejected" }))
  })

  it("throws a status-bearing error on a non-OK response", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(500, { detail: "boom" }))

    await expect(updateModerationItem("m1", "approved")).rejects.toThrow(/500/)
  })
})

describe("client — flagContent (hand-rolled mutation guard)", () => {
  beforeEach(() => {
    mockEmit.mockReset()
    vi.spyOn(globalThis, "fetch")
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("POSTs the entity descriptor and returns the created item", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      jsonResponse(200, { id: "m9", status: "pending" }),
    )

    const res = await flagContent("hadith", "bukhari:1", "mismatched grade")

    expect(res).toEqual({ id: "m9", status: "pending" })
    const [url, init] = vi.mocked(globalThis.fetch).mock.calls[0]!
    expect(url).toContain("/api/v1/admin/moderation/flag")
    const ri = init as RequestInit
    expect(ri.method).toBe("POST")
    expect(ri.body).toBe(
      JSON.stringify({
        entity_type: "hadith",
        entity_id: "bukhari:1",
        reason: "mismatched grade",
      }),
    )
  })

  it("throws a status-bearing error on a non-OK response", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(403, { detail: "forbidden" }))

    await expect(
      flagContent("hadith", "bukhari:1", "reason"),
    ).rejects.toThrow(/403/)
  })
})
