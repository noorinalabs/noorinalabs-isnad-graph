import { render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, it, expect, beforeEach, afterEach } from "vitest"

import AuthCallbackPage from "../AuthCallbackPage"

// AuthCallbackPage reads the access token from window.location.hash (the URL
// fragment) and reads the error/flag params via react-router's useSearchParams
// (the query string). MemoryRouter controls the query string via initialEntries;
// window.location.hash is set directly on the jsdom window since the component
// reads it off window, not the router.
function renderCallback(search: string) {
  return render(
    <MemoryRouter initialEntries={[`/auth/callback/google${search}`]}>
      <Routes>
        <Route path="/auth/callback/:provider" element={<AuthCallbackPage />} />
        <Route path="/" element={<div>home page</div>} />
        <Route path="/check-email" element={<div>check email page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

function setHash(hash: string) {
  // jsdom lets us assign location.hash; the component reads window.location.hash.
  window.location.hash = hash
}

describe("AuthCallbackPage — token source (#955: fragment-only, query ignored)", () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    setHash("")
  })

  afterEach(() => {
    setHash("")
  })

  it("stores the access token when it arrives in the URL fragment", async () => {
    setHash("#token=frag-token-abc")
    renderCallback("")

    await waitFor(() => {
      expect(screen.getByText("home page")).toBeInTheDocument()
    })
    expect(localStorage.getItem("access_token")).toBe("frag-token-abc")
  })

  it("IGNORES a token in the query string (the removed ?token= fallback, #955)", async () => {
    // Pre-#955 this query token would have been stored via the `?? searchParams`
    // fallback. Post-#955 the query string is untrusted for tokens — a token
    // here must NOT be persisted (re-opening the Referer-leak path #68 closed).
    setHash("")
    renderCallback("?token=query-token-should-be-ignored")

    await waitFor(() => {
      expect(screen.getByText("home page")).toBeInTheDocument()
    })
    expect(localStorage.getItem("access_token")).toBeNull()
  })

  it("uses the fragment token even when a query token is also present", async () => {
    // Belt-and-suspenders: if both are present, the fragment wins and the query
    // value is never read.
    setHash("#token=frag-wins")
    renderCallback("?token=query-loses")

    await waitFor(() => {
      expect(screen.getByText("home page")).toBeInTheDocument()
    })
    expect(localStorage.getItem("access_token")).toBe("frag-wins")
  })

  it("routes a new user needing verification to /check-email and stores the fragment token", async () => {
    setHash("#token=frag-token-new")
    renderCallback("?is_new_user=1&needs_verification=1")

    await waitFor(() => {
      expect(screen.getByText("check email page")).toBeInTheDocument()
    })
    expect(localStorage.getItem("access_token")).toBe("frag-token-new")
    expect(sessionStorage.getItem("is_new_user")).toBe("1")
  })

  it("renders the error UI for an error query param without storing any token", async () => {
    setHash("#token=should-not-be-read-on-error")
    renderCallback("?error=oauth_exchange_failed")

    await waitFor(() => {
      expect(screen.getByText("Sign-in failed")).toBeInTheDocument()
    })
    // On the error path the component returns before persisting the token.
    expect(localStorage.getItem("access_token")).toBeNull()
  })
})
