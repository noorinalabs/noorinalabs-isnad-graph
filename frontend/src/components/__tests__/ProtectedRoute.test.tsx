import { render, screen } from "@testing-library/react"
import { useEffect } from "react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, it, expect, vi, beforeEach } from "vitest"

import ProtectedRoute from "../ProtectedRoute"
import type { AuthUser } from "../../hooks/useAuth"

const mockUseAuth = vi.fn()
const mockUseSubscription = vi.fn()
vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
}))
vi.mock("../../hooks/useSubscription", () => ({
  useSubscription: () => mockUseSubscription(),
}))

function makeUser(overrides: Partial<AuthUser> = {}): AuthUser {
  return {
    id: "6cf04f80-ede7-42e6-9756-43f8ce8f220d",
    email: "jane@example.com",
    display_name: "Jane Smith",
    avatar_url: null,
    email_verified: true,
    is_active: true,
    locale: null,
    created_at: "2026-04-20T03:09:36.076621Z",
    roles: [],
    ...overrides,
  }
}

let mountCount = 0
function ChildPage() {
  useEffect(() => {
    mountCount += 1
  }, [])
  return <div>child page</div>
}

function renderProtected() {
  return render(
    <MemoryRouter initialEntries={["/app"]}>
      <Routes>
        <Route element={<ProtectedRoute />}>
          <Route path="/app" element={<ChildPage />} />
        </Route>
        <Route path="/login" element={<div>login page</div>} />
        <Route path="/trial-expired" element={<div>trial expired page</div>} />
        <Route path="/check-email" element={<div>check email page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    mockUseAuth.mockReset()
    mockUseSubscription.mockReset()
    mountCount = 0
  })

  it("redirects to /login when unauthenticated", () => {
    mockUseAuth.mockReturnValue({ user: null, loading: false })
    mockUseSubscription.mockReturnValue({ isExpired: false, isLoading: false })

    renderProtected()
    expect(screen.getByText("login page")).toBeInTheDocument()
  })

  it("redirects to /trial-expired when subscription is expired", () => {
    mockUseAuth.mockReturnValue({ user: makeUser(), loading: false })
    mockUseSubscription.mockReturnValue({ isExpired: true, isLoading: false })

    renderProtected()
    expect(screen.getByText("trial expired page")).toBeInTheDocument()
  })

  it("redirects to /check-email when email is unverified", () => {
    mockUseAuth.mockReturnValue({
      user: makeUser({ email_verified: false }),
      loading: false,
    })
    mockUseSubscription.mockReturnValue({ isExpired: false, isLoading: false })

    renderProtected()
    expect(screen.getByText("check email page")).toBeInTheDocument()
  })

  it("renders children for an authenticated, verified, non-expired user", () => {
    mockUseAuth.mockReturnValue({ user: makeUser(), loading: false })
    mockUseSubscription.mockReturnValue({ isExpired: false, isLoading: false })

    renderProtected()
    expect(screen.getByText("child page")).toBeInTheDocument()
  })

  it("keeps children mounted across a subLoading toggle (regression for #831)", () => {
    mockUseAuth.mockReturnValue({ user: makeUser(), loading: false })
    mockUseSubscription.mockReturnValue({ isExpired: false, isLoading: false })

    const { rerender } = renderProtected()
    expect(screen.getByText("child page")).toBeInTheDocument()
    expect(mountCount).toBe(1)

    // subLoading toggles true — e.g. the subscription query refetches.
    mockUseSubscription.mockReturnValue({ isExpired: false, isLoading: true })
    rerender(
      <MemoryRouter initialEntries={["/app"]}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/app" element={<ChildPage />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    // Child must NOT have unmounted/remounted — still mounted exactly once.
    expect(screen.getByText("child page")).toBeInTheDocument()
    expect(mountCount).toBe(1)

    // subLoading toggles back to false.
    mockUseSubscription.mockReturnValue({ isExpired: false, isLoading: false })
    rerender(
      <MemoryRouter initialEntries={["/app"]}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/app" element={<ChildPage />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByText("child page")).toBeInTheDocument()
    expect(mountCount).toBe(1)
  })
})
