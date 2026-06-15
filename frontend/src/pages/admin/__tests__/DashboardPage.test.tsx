import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import DashboardPage, { ObservabilitySection } from "../DashboardPage"
import { fetchDashboardStats } from "../../../api/admin-client"
import type { DashboardStats } from "../../../api/admin-client"
import { useAuth } from "../../../hooks/useAuth"
import { mintSsoCookie } from "../../../api/sso-client"

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

// The Observability section is admin-gated via useAuth().isAdmin; mock the hook so
// each test controls the role without standing up an AuthProvider.
vi.mock("../../../hooks/useAuth", () => ({
  useAuth: vi.fn(),
}))

// The SSO-cookie mint (POST /auth/sso-cookie) is mocked at the client boundary so
// the click tests assert the mint→navigate ordering without a real fetch.
vi.mock("../../../api/sso-client", () => ({
  mintSsoCookie: vi.fn(),
}))

function setAdmin(isAdmin: boolean) {
  vi.mocked(useAuth).mockReturnValue({
    isAdmin,
  } as unknown as ReturnType<typeof useAuth>)
}

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
    // Default to a non-admin context; admin-specific tests opt in via setAdmin(true).
    setAdmin(false)
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

  it("mounts the Observability section for an admin (ig#1081 re-enable)", async () => {
    setAdmin(true)
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

    await screen.findByText("Admin Dashboard")
    expect(screen.getByText("Observability")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /^Grafana/i })).toBeInTheDocument()
  })

  it("hides the Observability section for a non-admin", async () => {
    setAdmin(false)
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

describe("ObservabilitySection (ig#1081 SSO carry)", () => {
  let assignMock: ReturnType<typeof vi.fn>
  const realLocation = window.location

  beforeEach(() => {
    vi.clearAllMocks()
    // jsdom's `location.assign` is non-configurable (so it can't be spied
    // directly) and a real assign would throw "Not implemented: navigation".
    // Swap window.location for a stub exposing a mockable `assign`.
    assignMock = vi.fn()
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...realLocation, assign: assignMock, href: realLocation.href },
    })
  })

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: realLocation,
    })
  })

  it("renders three links with relative hrefs (no target=_blank — same-tab top-level nav)", () => {
    render(<ObservabilitySection />)

    expect(screen.getByText("Observability")).toBeTruthy()

    // Leading-word anchors avoid false-matches (e.g. the Logs description also
    // contains "Grafana").
    const grafanaLink = screen.getByRole("link", { name: /^Grafana/i })
    expect(grafanaLink).toHaveAttribute("href", "/grafana/")
    // The carry requires a top-level navigation in the SAME tab so SameSite=Lax
    // ships the parent-domain cookie — a new tab is no longer used.
    expect(grafanaLink).not.toHaveAttribute("target", "_blank")

    expect(screen.getByRole("link", { name: /^Logs/i })).toHaveAttribute(
      "href",
      "/grafana/explore",
    )
    expect(screen.getByRole("link", { name: /^Alerts/i })).toHaveAttribute(
      "href",
      "/grafana/alerting/list",
    )
  })

  it("mints the SSO cookie THEN navigates on an admin click", async () => {
    const user = userEvent.setup()
    vi.mocked(mintSsoCookie).mockResolvedValue({
      status: "ok",
      cookie_name: "nl_sso",
      expires_in: 300,
    })

    render(<ObservabilitySection />)
    await user.click(screen.getByRole("link", { name: /^Grafana/i }))

    await waitFor(() => {
      expect(assignMock).toHaveBeenCalledWith("/grafana/")
    })
    expect(mintSsoCookie).toHaveBeenCalledTimes(1)
    // Ordering: the mint must be invoked before the navigation fires.
    const order = (calls: number[]) => calls[0] ?? Infinity
    expect(order(vi.mocked(mintSsoCookie).mock.invocationCallOrder)).toBeLessThan(
      order(assignMock.mock.invocationCallOrder),
    )
    // No error surfaced.
    expect(screen.queryByRole("alert")).toBeNull()
  })

  it("shows an inline error and does NOT navigate when the mint fails", async () => {
    const user = userEvent.setup()
    vi.mocked(mintSsoCookie).mockRejectedValue(
      new Error("Your session has expired. Please sign in again."),
    )

    render(<ObservabilitySection />)
    await user.click(screen.getByRole("link", { name: /^Grafana/i }))

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /session has expired/i,
      )
    })
    expect(assignMock).not.toHaveBeenCalled()
  })

  it("ignores a second click while a mint is already in flight", async () => {
    const user = userEvent.setup()
    // Never-resolving mint keeps the first click pending.
    vi.mocked(mintSsoCookie).mockImplementation(() => new Promise(() => {}))

    render(<ObservabilitySection />)
    const link = screen.getByRole("link", { name: /^Grafana/i })
    await user.click(link)
    await user.click(link)

    await waitFor(() => {
      expect(mintSsoCookie).toHaveBeenCalledTimes(1)
    })
    expect(assignMock).not.toHaveBeenCalled()
  })
})
