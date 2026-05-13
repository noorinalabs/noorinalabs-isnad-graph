import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"

import { fetchSubscriptionOrNull } from "../client"

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

describe("fetchJson (via fetchSubscriptionOrNull) — allowStatuses", () => {
  beforeEach(() => {
    mockEmit.mockReset()
    vi.spyOn(globalThis, "fetch")
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("returns parsed body on 200", async () => {
    const payload = { tier: "trial", status: "trial", days_remaining: 5 }
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(200, payload))

    const result = await fetchSubscriptionOrNull()

    expect(result).toEqual(payload)
    expect(mockEmit).not.toHaveBeenCalled()
  })

  it("resolves null on an allowed status (404) instead of throwing", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(404, { detail: "not found" }))

    const result = await fetchSubscriptionOrNull()

    expect(result).toBeNull()
    expect(mockEmit).not.toHaveBeenCalled()
  })

  it("still throws on non-OK statuses outside the allow list (500)", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(500, { detail: "boom" }))

    await expect(fetchSubscriptionOrNull()).rejects.toThrow(/500/)
    expect(mockEmit).not.toHaveBeenCalled()
  })

  it("emits sessionExpired on 401 and still throws (401 not in allow list)", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse(401, { detail: "unauthorized" }))

    await expect(fetchSubscriptionOrNull()).rejects.toThrow(/401/)
    expect(mockEmit).toHaveBeenCalledTimes(1)
  })
})
