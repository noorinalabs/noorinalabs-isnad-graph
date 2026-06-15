import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import DataManagementPage from "../DataManagementPage"
import { fetchDataOverview, fetchDataSources, purgeSource } from "../../../api/admin-client"
import type { DataOverview, DataSources, PurgeResult } from "../../../types/admin"

vi.mock("../../../api/admin-client", () => ({
  fetchDataOverview: vi.fn(),
  fetchDataSources: vi.fn(),
  purgeSource: vi.fn(),
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
    // Scope to the provenance section: the danger-zone purge dropdown below also
    // renders the corpus names (as <option>s), so a bare getByText would be
    // ambiguous.
    const provSection = screen.getByText("Provenance by Source Corpus").closest("section")!
    expect(within(provSection).getByText("sunnah")).toBeInTheDocument()
    expect(within(provSection).getByText("40")).toBeInTheDocument()
    expect(within(provSection).getByText("thaqalayn")).toBeInTheDocument()
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

const PREVIEW: PurgeResult = {
  source_corpus: "thaqalayn",
  node_counts: [
    { label: "Hadith", count: 7 },
    { label: "Collection", count: 1 },
  ],
  relationship_counts: [{ rel_type: "APPEARS_IN", count: 7 }],
  total_nodes: 8,
  total_relationships: 7,
  dry_run: true,
  deleted: false,
}

describe("DataManagementPage — per-source purge (danger zone)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(fetchDataOverview).mockResolvedValue(OVERVIEW)
    vi.mocked(fetchDataSources).mockResolvedValue(SOURCES)
  })

  it("previews removal (dry run) and shows the per-label breakdown", async () => {
    const user = userEvent.setup()
    vi.mocked(purgeSource).mockResolvedValue(PREVIEW)
    renderPage()

    await screen.findByText("Danger Zone — Per-source Purge")
    // The dropdown options come from the (async) sources query.
    await screen.findByRole("option", { name: "thaqalayn" })
    await user.selectOptions(screen.getByLabelText("Source corpus"), "thaqalayn")
    await user.click(screen.getByRole("button", { name: "Preview removal" }))

    await screen.findByText("Dry-run preview")
    // Dry run is non-destructive — confirmation flag false.
    expect(purgeSource).toHaveBeenCalledWith("thaqalayn", true)
    expect(screen.getByText("Hadith: 7")).toBeInTheDocument()
    expect(screen.getByText("Collection: 1")).toBeInTheDocument()
  })

  it("keeps the purge disabled until the exact corpus name is typed, then executes", async () => {
    const user = userEvent.setup()
    vi.mocked(purgeSource)
      .mockResolvedValueOnce(PREVIEW)
      .mockResolvedValueOnce({ ...PREVIEW, dry_run: false, deleted: true })
    renderPage()

    await screen.findByText("Danger Zone — Per-source Purge")
    await screen.findByRole("option", { name: "thaqalayn" })
    await user.selectOptions(screen.getByLabelText("Source corpus"), "thaqalayn")
    await user.click(screen.getByRole("button", { name: "Preview removal" }))
    await screen.findByText("Dry-run preview")

    const purgeBtn = screen.getByRole("button", { name: "Purge graph data" })
    expect(purgeBtn).toBeDisabled()

    // A wrong token keeps it disabled.
    const confirm = screen.getByLabelText(/to confirm/)
    await user.type(confirm, "wrong")
    expect(purgeBtn).toBeDisabled()

    await user.clear(confirm)
    await user.type(confirm, "thaqalayn")
    expect(purgeBtn).toBeEnabled()

    await user.click(purgeBtn)
    await screen.findByText("Purge complete")
    // The real run carries the typed confirmation token.
    expect(purgeSource).toHaveBeenLastCalledWith("thaqalayn", false, "thaqalayn")
  })

  it("surfaces a backend error from the preview call", async () => {
    const user = userEvent.setup()
    vi.mocked(purgeSource).mockRejectedValue(new Error("purge boom"))
    renderPage()

    await screen.findByText("Danger Zone — Per-source Purge")
    await screen.findByRole("option", { name: "sunnah" })
    await user.selectOptions(screen.getByLabelText("Source corpus"), "sunnah")
    await user.click(screen.getByRole("button", { name: "Preview removal" }))

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Error: purge boom")
    })
  })
})
