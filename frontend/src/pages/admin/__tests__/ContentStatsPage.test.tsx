import { render, screen, waitFor } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import ContentStatsPage from "../ContentStatsPage"
import { fetchContentStats } from "../../../api/admin-client"
import type { ContentStats } from "../../../types/admin"

vi.mock("../../../api/admin-client", () => ({
  fetchContentStats: vi.fn(),
}))

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ContentStatsPage />
    </QueryClientProvider>,
  )
}

// Mirrors the loaded staging corpus: Sunni-only, with the totals matching the
// per-collection breakdown so the scope sentence is exercised end-to-end.
const SUNNI_ONLY: ContentStats = {
  hadith_count: 34028,
  narrator_count: 47199,
  collection_count: 7,
  coverage_pct: 99.86,
  sects: [{ sect: "sunni", hadith_count: 34028, collection_count: 7 }],
  collections: [
    { id: "muslim", name: "Sahih Muslim", sect: "sunni", hadith_count: 7314 },
    { id: "bukhari", name: "Sahih al-Bukhari", sect: "sunni", hadith_count: 7238 },
  ],
}

describe("ContentStatsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("shows loading state initially", () => {
    vi.mocked(fetchContentStats).mockImplementation(() => new Promise(() => {}))
    renderPage()
    expect(screen.getByText(/Loading/i)).toBeInTheDocument()
  })

  it("renders error state when the query fails", async () => {
    vi.mocked(fetchContentStats).mockRejectedValue(new Error("boom: stats down"))
    renderPage()
    await waitFor(() => {
      expect(screen.getByText(/Error: boom: stats down/)).toBeInTheDocument()
    })
  })

  it("renders the headline stat cards (locale-formatted)", async () => {
    vi.mocked(fetchContentStats).mockResolvedValue(SUNNI_ONLY)
    renderPage()

    expect(await screen.findByText("Hadiths")).toBeInTheDocument()
    // 34,028 appears both in the Hadiths card and the per-sect table cell.
    expect(screen.getAllByText("34,028").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Narrators")).toBeInTheDocument()
    expect(screen.getByText("47,199")).toBeInTheDocument()
    // Narrator caveat — the count must not be presented as distinct real narrators.
    expect(screen.getByText(/segmentation in progress/i)).toBeInTheDocument()
  })

  it("states corpus scope and does not imply completeness", async () => {
    vi.mocked(fetchContentStats).mockResolvedValue(SUNNI_ONLY)
    renderPage()

    // Scope sentence: "34,028 hadith across 7 collections — Sunni only."
    expect(
      await screen.findByText(/34,028 hadith across 7 collections — Sunni only\./),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/not a complete hadith corpus/i),
    ).toBeInTheDocument()
  })

  it("renders the per-sect and per-collection breakdown tables", async () => {
    vi.mocked(fetchContentStats).mockResolvedValue(SUNNI_ONLY)
    renderPage()

    expect(await screen.findByText("By sect")).toBeInTheDocument()
    expect(screen.getByText("By collection")).toBeInTheDocument()
    expect(screen.getByText("Sahih Muslim")).toBeInTheDocument()
    expect(screen.getByText("Sahih al-Bukhari")).toBeInTheDocument()
    expect(screen.getByText("7,314")).toBeInTheDocument()
  })

  it("omits breakdown tables when nothing is loaded", async () => {
    vi.mocked(fetchContentStats).mockResolvedValue({
      hadith_count: 0,
      narrator_count: 0,
      collection_count: 0,
      coverage_pct: 0,
      sects: [],
      collections: [],
    })
    renderPage()

    expect(await screen.findByText("Hadiths")).toBeInTheDocument()
    expect(screen.queryByText("By sect")).not.toBeInTheDocument()
    expect(screen.queryByText("By collection")).not.toBeInTheDocument()
  })
})
