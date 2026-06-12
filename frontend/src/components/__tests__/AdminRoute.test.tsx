import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, it, expect, vi, beforeEach } from "vitest"

import AdminRoute from "../AdminRoute"
import type { UserRole } from "../../hooks/useAuth"

const mockUseAuth = vi.fn()
vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
}))

// Stub matching the shape AdminRoute reads: `hasRole` + `loading`. `hasRole`
// is derived from a granted role so the guard logic (not a hand-wired boolean)
// is what's under test.
function authStub(role: UserRole, loading = false) {
  const RANK: Record<UserRole, number> = {
    trial: 0,
    reader: 1,
    researcher: 2,
    admin: 3,
  }
  return {
    loading,
    hasRole: (min: UserRole) => RANK[role] >= RANK[min],
  }
}

function renderAdmin() {
  return render(
    <MemoryRouter initialEntries={["/admin"]}>
      <Routes>
        <Route path="/" element={<div>home page</div>} />
        <Route element={<AdminRoute />}>
          <Route path="/admin" element={<div>admin content</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe("AdminRoute", () => {
  beforeEach(() => {
    mockUseAuth.mockReset()
  })

  it("renders the admin outlet for an admin user", () => {
    mockUseAuth.mockReturnValue(authStub("admin"))

    renderAdmin()
    expect(screen.getByText("admin content")).toBeInTheDocument()
  })

  it("silently redirects a non-admin user to home (no 403 panel) — ig#804", () => {
    mockUseAuth.mockReturnValue(authStub("researcher"))

    renderAdmin()
    expect(screen.getByText("home page")).toBeInTheDocument()
    expect(screen.queryByText("admin content")).not.toBeInTheDocument()
    // The old 403 forbidden panel must be gone — non-admins should not even
    // learn the admin area exists.
    expect(screen.queryByText("403")).not.toBeInTheDocument()
  })

  it("renders nothing (no premature redirect) while auth is still loading", () => {
    mockUseAuth.mockReturnValue(authStub("admin", /* loading */ true))

    renderAdmin()
    // Neither the admin content nor a redirect home — we wait for auth to settle
    // so an admin reloading on /admin is not bounced during the null-user window.
    expect(screen.queryByText("admin content")).not.toBeInTheDocument()
    expect(screen.queryByText("home page")).not.toBeInTheDocument()
  })
})
