import { render, screen, waitFor } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import DashboardPage from "../DashboardPage"
import { fetchDashboardStats } from "../../../api/admin-client"
import type { DashboardStats } from "../../../api/admin-client"

// Role names are kept as variables, NOT literals, so the tests survive the
// pending UserRole vocab change in #876 (viewer/editor/moderator → trial/reader/researcher).
// DashboardPage itself is vocab-agnostic — it iterates `data.users_by_role` and renders
// whatever the API returns.
const ROLE_A = "researcher"
const ROLE_B = "reader"
const ROLE_ADMIN = "admin"

vi.mock("../../../api/admin-client", () => ({
  fetchDashboardStats: vi.fn(),
}))

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <DashboardPage />
    </QueryClientProvider>,
  )
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("shows loading state initially", () => {
    vi.mocked(fetchDashboardStats).mockImplementation(
      () => new Promise(() => {}),
    )
    renderPage()
    expect(screen.getByText(/Loading dashboard/i)).toBeInTheDocument()
  })

  it("renders error state when the query fails", async () => {
    vi.mocked(fetchDashboardStats).mockRejectedValue(
      new Error("boom: stats unreachable"),
    )
    renderPage()
    await waitFor(() => {
      expect(
        screen.getByText(/Error: boom: stats unreachable/),
      ).toBeInTheDocument()
    })
  })

  it("renders all StatCards when user stats are present", async () => {
    const stats: DashboardStats = {
      total_users: 1234,
      active_users: 987,
      suspended_users: 12,
      new_registrations_7d: 45,
      active_sessions: 56,
      users_by_role: [
        { role: ROLE_A, count: 100 },
        { role: ROLE_B, count: 50 },
        { role: ROLE_ADMIN, count: 3 },
      ],
    }
    vi.mocked(fetchDashboardStats).mockResolvedValue(stats)
    renderPage()

    expect(await screen.findByText("Admin Dashboard")).toBeInTheDocument()
    expect(screen.getByText("Total Users")).toBeInTheDocument()
    expect(screen.getByText("1234")).toBeInTheDocument()
    expect(screen.getByText("Active Users")).toBeInTheDocument()
    expect(screen.getByText("987")).toBeInTheDocument()
    expect(screen.getByText("Suspended Users")).toBeInTheDocument()
    expect(screen.getByText("12")).toBeInTheDocument()
    expect(screen.getByText("New (7d)")).toBeInTheDocument()
    expect(screen.getByText("45")).toBeInTheDocument()
    expect(screen.getByText("Active Sessions")).toBeInTheDocument()
    expect(screen.getByText("56")).toBeInTheDocument()
  })

  it("renders the users-by-role table when the list is non-empty", async () => {
    const stats: DashboardStats = {
      total_users: 100,
      active_sessions: 5,
      users_by_role: [
        { role: ROLE_A, count: 60 },
        { role: ROLE_B, count: 30 },
        { role: ROLE_ADMIN, count: 10 },
      ],
    }
    vi.mocked(fetchDashboardStats).mockResolvedValue(stats)
    renderPage()

    await screen.findByText("Users by Role")
    expect(screen.getByRole("columnheader", { name: "Role" })).toBeInTheDocument()
    expect(screen.getByRole("columnheader", { name: "Count" })).toBeInTheDocument()
    expect(screen.getByText(ROLE_A)).toBeInTheDocument()
    expect(screen.getByText("60")).toBeInTheDocument()
    expect(screen.getByText(ROLE_B)).toBeInTheDocument()
    expect(screen.getByText("30")).toBeInTheDocument()
    expect(screen.getByText(ROLE_ADMIN)).toBeInTheDocument()
    expect(screen.getByText("10")).toBeInTheDocument()
  })

  it("omits a StatCard when the corresponding field is undefined", async () => {
    const stats: DashboardStats = {
      // total_users / active_users / suspended_users / new_registrations_7d omitted
      active_sessions: 7,
      users_by_role: [{ role: ROLE_ADMIN, count: 1 }],
    }
    vi.mocked(fetchDashboardStats).mockResolvedValue(stats)
    renderPage()

    await screen.findByText("Active Sessions")
    expect(screen.queryByText("Total Users")).not.toBeInTheDocument()
    expect(screen.queryByText("Active Users")).not.toBeInTheDocument()
    expect(screen.queryByText("Suspended Users")).not.toBeInTheDocument()
    expect(screen.queryByText("New (7d)")).not.toBeInTheDocument()
    expect(screen.getByText("Active Sessions")).toBeInTheDocument()
    expect(screen.getByText("7")).toBeInTheDocument()
  })

  it("renders the cross-service migration placeholder when user stats are absent and users_by_role is empty", async () => {
    const stats: DashboardStats = {
      active_sessions: 9,
      users_by_role: [],
    }
    vi.mocked(fetchDashboardStats).mockResolvedValue(stats)
    renderPage()

    await screen.findByText("Active Sessions")
    expect(
      screen.getByText(/User statistics have moved to user-service/i),
    ).toBeInTheDocument()
    expect(screen.getByText(/see #806/)).toBeInTheDocument()
    expect(screen.queryByText("Users by Role")).not.toBeInTheDocument()
  })

  it("does NOT render the placeholder when any user-stat field is present, even with empty users_by_role", async () => {
    const stats: DashboardStats = {
      total_users: 5,
      active_sessions: 1,
      users_by_role: [],
    }
    vi.mocked(fetchDashboardStats).mockResolvedValue(stats)
    renderPage()

    await screen.findByText("Total Users")
    expect(
      screen.queryByText(/User statistics have moved to user-service/i),
    ).not.toBeInTheDocument()
    expect(screen.queryByText("Users by Role")).not.toBeInTheDocument()
  })

  it("treats `data === null` as a no-op render (returns null branch)", async () => {
    vi.mocked(fetchDashboardStats).mockResolvedValue(null as never)
    const { container } = renderPage()
    await waitFor(() => {
      // Once the query resolves, the loading text disappears and the component returns null
      expect(screen.queryByText(/Loading dashboard/i)).not.toBeInTheDocument()
    })
    expect(container.querySelector("h2")).toBeNull()
  })
})
