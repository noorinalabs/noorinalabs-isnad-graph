import { render, screen, waitFor } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import DashboardPage, { ObservabilitySection } from "../DashboardPage"
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

  it("renders all StatCards from the real user counts", async () => {
    const stats: DashboardStats = {
      total_users: 1234,
      active_users: 987,
      deactivated_users: 12,
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
    // Counts are locale-formatted (thousands separators).
    expect(screen.getByText("1,234")).toBeInTheDocument()
    expect(screen.getByText("Active Users")).toBeInTheDocument()
    expect(screen.getByText("987")).toBeInTheDocument()
    expect(screen.getByText("Deactivated Users")).toBeInTheDocument()
    expect(screen.getByText("12")).toBeInTheDocument()
    expect(screen.getByText("New (7d)")).toBeInTheDocument()
    expect(screen.getByText("45")).toBeInTheDocument()
    expect(screen.getByText("Active Sessions")).toBeInTheDocument()
    expect(screen.getByText("56")).toBeInTheDocument()
  })

  it("renders the users-by-role table when the list is non-empty", async () => {
    const stats: DashboardStats = {
      total_users: 100,
      active_users: 100,
      deactivated_users: 0,
      new_registrations_7d: 0,
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

  it("omits the users-by-role table when the role list is empty", async () => {
    const stats: DashboardStats = {
      total_users: 5,
      active_users: 5,
      deactivated_users: 0,
      new_registrations_7d: 1,
      active_sessions: 1,
      users_by_role: [],
    }
    vi.mocked(fetchDashboardStats).mockResolvedValue(stats)
    renderPage()

    await screen.findByText("Total Users")
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

  it("does NOT mount the Observability section while gated off (ig#1073)", async () => {
    // The obs-links are hidden until the Grafana SSO bridge ships (deploy#458):
    // until then they dead-end at Grafana's login. Assert the section is absent
    // from the rendered dashboard. Re-enable assertion when deploy#458 lands.
    const stats: DashboardStats = {
      total_users: 10,
      active_users: 10,
      deactivated_users: 0,
      new_registrations_7d: 0,
      active_sessions: 1,
      users_by_role: [],
    }
    vi.mocked(fetchDashboardStats).mockResolvedValue(stats)
    renderPage()

    // Dashboard has rendered (stats visible) but the Observability section is not.
    await screen.findByText("Admin Dashboard")
    expect(screen.queryByText("Observability")).toBeNull()
    expect(screen.queryByRole("link", { name: /^Grafana/i })).toBeNull()
  })
})

describe("ObservabilitySection (gated component, ig#1073)", () => {
  // The section is mounted off-page for now, but its markup must stay correct so
  // flipping OBSERVABILITY_LINKS_ENABLED back on (when deploy#458 ships) is safe.
  it("renders three links with relative hrefs, target=_blank, rel=noopener", () => {
    render(<ObservabilitySection />)

    expect(screen.getByText("Observability")).toBeTruthy()

    // Leading-word anchors avoid false-matches (e.g. the Logs description also
    // contains "Grafana").
    const grafanaLink = screen.getByRole("link", { name: /^Grafana/i })
    expect(grafanaLink).toHaveAttribute("href", "/grafana/")
    expect(grafanaLink).toHaveAttribute("target", "_blank")
    expect(grafanaLink).toHaveAttribute("rel", "noopener noreferrer")

    const logsLink = screen.getByRole("link", { name: /^Logs/i })
    expect(logsLink).toHaveAttribute("href", "/grafana/explore")
    expect(logsLink).toHaveAttribute("target", "_blank")
    expect(logsLink).toHaveAttribute("rel", "noopener noreferrer")

    const alertsLink = screen.getByRole("link", { name: /^Alerts/i })
    expect(alertsLink).toHaveAttribute("href", "/grafana/alerting/list")
    expect(alertsLink).toHaveAttribute("target", "_blank")
    expect(alertsLink).toHaveAttribute("rel", "noopener noreferrer")
  })
})
