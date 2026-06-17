import { render, screen, waitFor } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"

import { AuthProvider, useAuth } from "../useAuth"

// The token-refresh path is only exercised on a 401; mock it so it never
// reaches a real network call and so a 401 deterministically yields "no token".
vi.mock("../../api/token-refresh", () => ({
  refreshAccessToken: vi.fn(async () => null),
}))

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  })
}

// A reverse-proxy fallback / misrouted origin answering 200 with the SPA
// index.html instead of JSON — the deploy#420 class that ig#993 guards against.
function htmlResponse(): Response {
  return new Response("<!DOCTYPE html><html><body>SPA</body></html>", {
    status: 200,
    headers: { "Content-Type": "text/html" },
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

describe("AuthProvider boot load — readJsonResponse guard (ig#993)", () => {
  beforeEach(() => {
    localStorage.setItem("access_token", "tok")
  })

  afterEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it("loads the user when /users/me answers with JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ id: "1", email: "jane@example.com", roles: [] })),
    )

    renderProvider()

    await waitFor(() => expect(screen.getByText("user:jane@example.com")).toBeInTheDocument())
  })

  it("degrades to unauthenticated (not a stuck spinner) on a non-JSON 200", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => htmlResponse()))

    renderProvider()

    // The bare `res.json()` would have thrown an unhandled SyntaxError, leaving
    // `loading` true forever. The guard turns it into a clean "anon" state.
    await waitFor(() => expect(screen.getByText("anon")).toBeInTheDocument())
  })
})
