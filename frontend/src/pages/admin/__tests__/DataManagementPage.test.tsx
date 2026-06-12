import { render, screen, waitFor } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import DataManagementPage from "../DataManagementPage"
import { fetchDataOverview, fetchDataSources } from "../../../api/admin-client"
import type { DataOverview, DataSources } from "../../../types/admin"

vi.mock("../../../api/admin-client", () => ({
  fetchDataOverview: vi.fn(),
  fetchDataSources: vi.fn(),
}))

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <DataManagementPage />
    </QueryClientProvider>,
  )
}

const OVERVIEW: DataOverview = {
  node_counts: [
    { label: "Narrator", count: 120 },
    { label: "Hadith", count: 47 },
  ],
  relationship_counts: [{ rel_type: "NARRATED", count: 200 }],
  total_nodes: 167,
  total_relationships: 200,
}

const SOURCES: DataSources = {
  sources: [
    { source_corpus: "sunnah", hadith_count: 40, collection_count: 2 },
    { source_corpus: "thaqalayn", hadith_count: 7, collection_count: 1 },
  ],
  total_hadiths: 47,
  total_collections: 3,
  distinct_sources: 2,
}

describe("DataManagementPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("shows loading state initially", () => {
    vi.mocked(fetchDataOverview).mockImplementation(() => new Promise(() => {}))
    vi.mocked(fetchDataSources).mockImplementation(() => new Promise(() => {}))
    renderPage()
    expect(screen.getByText("Data Management")).toBeInTheDocument()
    expect(screen.getAllByText(/Loading\.\.\./).length).toBeGreaterThan(0)
  })

  it("renders an error state when the overview query fails", async () => {
    vi.mocked(fetchDataOverview).mockRejectedValue(new Error("overview boom"))
    vi.mocked(fetchDataSources).mockResolvedValue(SOURCES)
    renderPage()
    await waitFor(() => {
      expect(screen.getByText(/Error: overview boom/)).toBeInTheDocument()
    })
  })

  it("renders inventory totals and per-label/type tables", async () => {
    vi.mocked(fetchDataOverview).mockResolvedValue(OVERVIEW)
    vi.mocked(fetchDataSources).mockResolvedValue(SOURCES)
    renderPage()

    await screen.findByText("Total Nodes")
    expect(screen.getByText("167")).toBeInTheDocument()
    expect(screen.getByText("Total Relationships")).toBeInTheDocument()
    expect(screen.getByText("Nodes by Label")).toBeInTheDocument()
    expect(screen.getByText("Narrator")).toBeInTheDocument()
    expect(screen.getByText("120")).toBeInTheDocument()
    expect(screen.getByText("Relationships by Type")).toBeInTheDocument()
    expect(screen.getByText("NARRATED")).toBeInTheDocument()
  })

  it("renders the provenance breakdown by source corpus", async () => {
    vi.mocked(fetchDataOverview).mockResolvedValue(OVERVIEW)
    vi.mocked(fetchDataSources).mockResolvedValue(SOURCES)
    renderPage()

    await screen.findByText("Distinct Sources")
    expect(screen.getByText("Provenance by Source Corpus")).toBeInTheDocument()
    expect(screen.getByText("sunnah")).toBeInTheDocument()
    expect(screen.getByText("40")).toBeInTheDocument()
    expect(screen.getByText("thaqalayn")).toBeInTheDocument()
  })

  it("shows empty-state copy when nothing is loaded", async () => {
    vi.mocked(fetchDataOverview).mockResolvedValue({
      node_counts: [],
      relationship_counts: [],
      total_nodes: 0,
      total_relationships: 0,
    })
    vi.mocked(fetchDataSources).mockResolvedValue({
      sources: [],
      total_hadiths: 0,
      total_collections: 0,
      distinct_sources: 0,
    })
    renderPage()

    await waitFor(() => {
      expect(screen.getByText("No nodes loaded.")).toBeInTheDocument()
    })
    expect(screen.getByText("No relationships loaded.")).toBeInTheDocument()
    expect(screen.getByText("No source-attributed content loaded.")).toBeInTheDocument()
  })
})
