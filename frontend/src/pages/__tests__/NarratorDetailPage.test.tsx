import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter, Route, Routes } from "react-router-dom"

import NarratorDetailPage from "../NarratorDetailPage"
import type { Narrator, NarratorChainsResponse } from "../../types/api"

// NarratorDetailPage fans out three useQuery calls (narrator / chains /
// network) keyed off the :id route param. We mock the api/client module and
// drive the page through its loading -> error / not-found / loaded states,
// plus the client-side hadith pagination.
vi.mock("../../api/client", () => ({
  fetchNarrator: vi.fn(),
  fetchNarratorChains: vi.fn(),
  fetchGraphNetwork: vi.fn(),
}))

import {
  fetchNarrator,
  fetchNarratorChains,
  fetchGraphNetwork,
} from "../../api/client"

const mockFetchNarrator = fetchNarrator as ReturnType<typeof vi.fn>
const mockFetchChains = fetchNarratorChains as ReturnType<typeof vi.fn>
const mockFetchNetwork = fetchGraphNetwork as ReturnType<typeof vi.fn>

function makeNarrator(overrides: Partial<Narrator> = {}): Narrator {
  return {
    id: "malik",
    name_ar: "مالك بن أنس",
    name_en: "Malik ibn Anas",
    kunya: "Abu Abdullah",
    nisba: "al-Asbahi",
    laqab: null,
    birth_year_ah: 93,
    death_year_ah: 179,
    generation: "Tabi al-Tabiin",
    gender: "male",
    sect_affiliation: "Sunni",
    trustworthiness_consensus: "Thiqah",
    aliases: [],
    betweenness_centrality: 0.1234,
    in_degree: 12,
    out_degree: 8,
    pagerank: 0.0456,
    community_id: 3,
    ...overrides,
  }
}

function makeChains(count: number): NarratorChainsResponse {
  return {
    narrator_id: "malik",
    total: count,
    chains: Array.from({ length: count }, (_, i) => ({
      chain_id: `c${i}`,
      hadith_id: `h${i}`,
      matn_ar: `متن ${i}`,
      matn_en: `matn ${i}`,
      grade: i % 2 === 0 ? "Sahih" : null,
    })),
  }
}

const NETWORK = {
  narrator_id: "malik",
  nodes: [{ id: "a" }, { id: "b" }, { id: "c" }],
  edges: [],
  teachers: 12,
  students: 8,
}

function renderPage(id = "malik") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/narrators/${id}`]}>
        <Routes>
          <Route path="/narrators/:id" element={<NarratorDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("NarratorDetailPage", () => {
  beforeEach(() => {
    mockFetchNarrator.mockReset()
    mockFetchChains.mockReset()
    mockFetchNetwork.mockReset()
  })

  it("renders the narrator profile once the primary query resolves", async () => {
    mockFetchNarrator.mockResolvedValue(makeNarrator())
    mockFetchChains.mockResolvedValue(makeChains(0))
    mockFetchNetwork.mockResolvedValue(NETWORK)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText("مالك بن أنس")).toBeInTheDocument()
    })
    // English name, profile metadata, and reliability aggregate all render.
    expect(screen.getAllByText("Malik ibn Anas").length).toBeGreaterThan(0)
    expect(screen.getByText("Abu Abdullah")).toBeInTheDocument()
    expect(screen.getByText(/Aggregate: Thiqah/)).toBeInTheDocument()
  })

  it("passes the route :id param through to the data fetchers", async () => {
    mockFetchNarrator.mockResolvedValue(makeNarrator({ id: "shafii" }))
    mockFetchChains.mockResolvedValue(makeChains(0))
    mockFetchNetwork.mockResolvedValue(NETWORK)

    renderPage("shafii")

    await waitFor(() => expect(mockFetchNarrator).toHaveBeenCalledWith("shafii"))
    expect(mockFetchChains).toHaveBeenCalledWith("shafii")
    expect(mockFetchNetwork).toHaveBeenCalledWith("shafii", 1)
  })

  it("surfaces an error message when the primary query rejects", async () => {
    mockFetchNarrator.mockRejectedValue(new Error("upstream exploded"))
    mockFetchChains.mockResolvedValue(makeChains(0))
    mockFetchNetwork.mockResolvedValue(NETWORK)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText(/Error: upstream exploded/)).toBeInTheDocument()
    })
  })

  it("shows a not-found message when the narrator query resolves to null", async () => {
    // The API client is typed non-null, but a null body is a real runtime
    // possibility the page explicitly guards against.
    mockFetchNarrator.mockResolvedValue(null)
    mockFetchChains.mockResolvedValue(makeChains(0))
    mockFetchNetwork.mockResolvedValue(NETWORK)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText("Narrator not found.")).toBeInTheDocument()
    })
  })

  it("renders the network preview stats from the network query", async () => {
    mockFetchNarrator.mockResolvedValue(makeNarrator())
    mockFetchChains.mockResolvedValue(makeChains(0))
    mockFetchNetwork.mockResolvedValue(NETWORK)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText("3 nodes in ego-graph")).toBeInTheDocument()
    })
    expect(screen.getByText(/Teachers: 12 \| Students: 8/)).toBeInTheDocument()
  })

  it("does not render the hadith list when the narrator has no chains", async () => {
    mockFetchNarrator.mockResolvedValue(makeNarrator())
    mockFetchChains.mockResolvedValue(makeChains(0))
    mockFetchNetwork.mockResolvedValue(NETWORK)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText("مالك بن أنس")).toBeInTheDocument()
    })
    expect(screen.queryByText(/Hadith Narrated/)).not.toBeInTheDocument()
  })

  it("paginates the hadith list client-side at 10 per page", async () => {
    mockFetchNarrator.mockResolvedValue(makeNarrator())
    // 12 chains -> 2 pages (10 per page).
    mockFetchChains.mockResolvedValue(makeChains(12))
    mockFetchNetwork.mockResolvedValue(NETWORK)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText("Hadith Narrated (12 total)")).toBeInTheDocument()
    })

    // Page 1: first 10 hadiths present, 11th not yet.
    expect(screen.getByText("Hadith h0")).toBeInTheDocument()
    expect(screen.getByText("Hadith h9")).toBeInTheDocument()
    expect(screen.queryByText("Hadith h10")).not.toBeInTheDocument()
    expect(screen.getByText("1 of 2")).toBeInTheDocument()

    // Advance to page 2 — the remaining 2 hadiths show, the first 10 don't.
    await userEvent.click(screen.getByRole("button", { name: "Next" }))

    await waitFor(() => {
      expect(screen.getByText("Hadith h10")).toBeInTheDocument()
    })
    expect(screen.getByText("Hadith h11")).toBeInTheDocument()
    expect(screen.queryByText("Hadith h0")).not.toBeInTheDocument()
    expect(screen.getByText("2 of 2")).toBeInTheDocument()
  })
})
