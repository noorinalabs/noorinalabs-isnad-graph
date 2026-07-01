import { render, screen, waitFor } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"

import { AuthProvider, useAuth } from "../useAuth"
import { refreshAccessToken } from "../../api/token-refresh"

// Deep-link / hard-refresh hydration race (#1111): on a cold load the
// short-lived access token can be absent from localStorage while the httpOnly
// refresh cookie is still valid. The boot loader MUST attempt a cookie-based
// refresh before deciding the user is unauthenticated. We mock the refresh
// exchange so the "valid refresh cookie" case is deterministic.
vi.mock("../../api/token-refresh", () => ({
  refreshAccessToken: vi.fn(),
}))

const mockRefresh = vi.mocked(refreshAccessToken)

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  })
}

function unauthorizedResponse(): Response {
  return new Response(JSON.stringify({ detail: "unauthorized" }), {
    status: 401,
    headers: { "Content-Type": "application/json" },
  })
}

function Probe() {
  const { loading, user } = useAuth()
  if (loading) return <div>loading</div>
  return <div>{user ? `user:${user.email}` : "anon"}</div>
}

function renderProvider() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  )
}

describe("AuthProvider boot load — deep-link/refresh hydration race (#1111)", () => {
  beforeEach(() => {
    localStorage.clear()
    mockRefresh.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it("hydrates a valid session on a cold deep-link when no access token is in localStorage", async () => {
    // No access_token persisted (the deep-link / hard-refresh case)…
    expect(localStorage.getItem("access_token")).toBeNull()
    // …but the httpOnly refresh cookie is still valid, so the exchange succeeds.
    mockRefresh.mockResolvedValue("fresh-access-token")

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString()
      if (url.endsWith("/api/v1/users/me")) {
        return jsonResponse({ id: "1", email: "jane@example.com", roles: [] })
      }
      throw new Error(`unexpected fetch: ${url}`)
    })
    vi.stubGlobal("fetch", fetchMock)

    renderProvider()

    // Pre-fix: loadUser bailed on the missing token without refreshing, so the
    // guard saw a null user and the session was bounced ("anon"). Post-fix the
    // cookie-based refresh runs first and the user hydrates — staying signed in.
    await waitFor(() => expect(screen.getByText("user:jane@example.com")).toBeInTheDocument())

    // Exactly one refresh exchange — no per-render/per-call storm that would
    // mint duplicate sessions (guards against session accumulation).
    expect(mockRefresh).toHaveBeenCalledTimes(1)
  })

  it("degrades to anon (does not loop) when there is no access token AND no valid refresh cookie", async () => {
    expect(localStorage.getItem("access_token")).toBeNull()
    // No valid refresh cookie — the exchange fails closed.
    mockRefresh.mockResolvedValue(null)

    const fetchMock = vi.fn(async () => unauthorizedResponse())
    vi.stubGlobal("fetch", fetchMock)

    renderProvider()

    await waitFor(() => expect(screen.getByText("anon")).toBeInTheDocument())

    // One refresh attempt, then give up — never fetch /me without a token.
    expect(mockRefresh).toHaveBeenCalledTimes(1)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
