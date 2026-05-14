import { render, screen } from "@testing-library/react"
import { MemoryRouter, Routes, Route } from "react-router-dom"
import { describe, it, expect, vi, beforeEach } from "vitest"

import AdminLayout from "../AdminLayout"
import type { AuthUser } from "../../hooks/useAuth"

const mockUseAuth = vi.fn()
vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
}))

vi.mock("../ThemeToggle", () => ({
  default: () => <div data-testid="theme-toggle" />,
}))

function makeAdmin(): AuthUser {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    email: "admin@example.com",
    display_name: "Admin",
    avatar_url: null,
    email_verified: true,
    is_active: true,
    locale: null,
    created_at: "2026-04-20T03:09:36.076621Z",
    roles: ["admin"],
  }
}

function renderAdminLayout() {
  return render(
    <MemoryRouter initialEntries={["/admin/dashboard"]}>
      <Routes>
        <Route path="/admin/*" element={<AdminLayout />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe("AdminLayout nav", () => {
  beforeEach(() => {
    mockUseAuth.mockReset()
    mockUseAuth.mockReturnValue({
      user: makeAdmin(),
      loading: false,
      isAdmin: true,
    })
  })

  it("does not render the User Management entry while backend returns 501 (#835)", () => {
    renderAdminLayout()
    expect(screen.queryByRole("link", { name: "User Management" })).toBeNull()
  })

  it("renders the remaining admin nav entries", () => {
    renderAdminLayout()
    for (const label of [
      "Dashboard",
      "System Health",
      "Content Stats",
      "Usage Analytics",
      "Audit Log",
    ]) {
      expect(
        screen.getByRole("link", { name: label }),
      ).toBeInTheDocument()
    }
  })
})
