import { render, screen, waitFor, fireEvent, act } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import HadithsPage from "../HadithsPage"
import {
  fetchHadiths,
  fetchCollections,
  fetchHadithFacets,
  fetchNarrators,
} from "../../api/client"
import type {
  PaginatedResponse,
  Hadith,
  Narrator,
  Collection,
} from "../../types/api"

vi.mock("../../api/client", () => ({
  fetchHadiths: vi.fn(),
  fetchCollections: vi.fn(),
  fetchHadithFacets: vi.fn(),
  fetchNarrators: vi.fn(),
}))

function hadithsPage(narratorApplied = false): PaginatedResponse<Hadith> {
  return {
    items: [
      {
        id: "hdt:lk:bukhari:1:1",
        matn_ar: "إنما الأعمال بالنيات",
        matn_en: "Actions are by intentions",
        isnad_raw_ar: null,
        isnad_raw_en: null,
        grade_composite: "sahih",
        grade_normalized: "sahih",
        topic_tags: [],
        source_corpus: "lk",
        collection_name: "Bukhari",
        display_title: "Bukhari 1:1",
        has_sunni_parallel: false,
        has_shia_parallel: false,
      },
    ],
    total: narratorApplied ? 1 : 5,
    page: 1,
    limit: 25,
  }
}

function narratorPage(): PaginatedResponse<Narrator> {
  return {
    items: [
      {
        id: "nar:az-zuhri-0001",
        name_ar: "محمد بن مسلم الزهري",
        name_en: "Ibn Shihab al-Zuhri",
        kunya: null,
        nisba: null,
        laqab: null,
        birth_year_ah: null,
        death_year_ah: null,
        generation: "tabi_tabiin",
        gender: "male",
        sect_affiliation: "sunni",
        trustworthiness_consensus: "thiqa",
        aliases: [],
        betweenness_centrality: null,
        in_degree: null,
        out_degree: null,
        pagerank: null,
        community_id: null,
      },
    ],
    total: 1,
    page: 1,
    limit: 8,
  }
}

const emptyCollections: PaginatedResponse<Collection> = {
  items: [],
  total: 0,
  page: 1,
  limit: 100,
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <HadithsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("HadithsPage narrator-in-isnad filter (#1050)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(fetchHadiths).mockResolvedValue(hadithsPage(false))
    vi.mocked(fetchCollections).mockResolvedValue(emptyCollections)
    vi.mocked(fetchHadithFacets).mockResolvedValue({ source_corpus: [], grades: [] })
    vi.mocked(fetchNarrators).mockResolvedValue(narratorPage())
  })

  it("queries narrator suggestions (debounced) once the input has >= 2 chars", async () => {
    renderPage()
    const input = await screen.findByRole("combobox", {
      name: /filter by isnad narrator/i,
    })
    fireEvent.change(input, { target: { value: "Zu" } })
    await waitFor(() => {
      expect(fetchNarrators).toHaveBeenCalledWith(1, 8, "Zu")
    })
    expect(await screen.findByText("Ibn Shihab al-Zuhri")).toBeInTheDocument()
  })

  it("does NOT query suggestions for a single character", async () => {
    renderPage()
    const input = await screen.findByRole("combobox", {
      name: /filter by isnad narrator/i,
    })
    fireEvent.change(input, { target: { value: "Z" } })
    // Let the debounce window (and its resulting state update) elapse.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 350))
    })
    expect(fetchNarrators).not.toHaveBeenCalled()
  })

  it("applies the narrator filter to fetchHadiths when a suggestion is picked", async () => {
    renderPage()
    const input = await screen.findByRole("combobox", {
      name: /filter by isnad narrator/i,
    })
    fireEvent.change(input, { target: { value: "Zuh" } })
    const option = await screen.findByText("Ibn Shihab al-Zuhri")

    vi.mocked(fetchHadiths).mockResolvedValue(hadithsPage(true))
    fireEvent.click(option)

    await waitFor(() => {
      const calls = vi.mocked(fetchHadiths).mock.calls
      const last = calls[calls.length - 1]!
      expect(last[2]).toMatchObject({ narrator: "nar:az-zuhri-0001" })
    })
    // The selection collapses into a removable chip showing the narrator name.
    expect(
      screen.getByRole("button", { name: /remove narrator filter/i }),
    ).toBeInTheDocument()
    expect(screen.getByText("Ibn Shihab al-Zuhri")).toBeInTheDocument()
  })

  it("clears the narrator filter via the chip remove button", async () => {
    renderPage()
    const input = await screen.findByRole("combobox", {
      name: /filter by isnad narrator/i,
    })
    fireEvent.change(input, { target: { value: "Zuh" } })
    fireEvent.click(await screen.findByText("Ibn Shihab al-Zuhri"))

    const remove = await screen.findByRole("button", {
      name: /remove narrator filter/i,
    })
    fireEvent.click(remove)

    await waitFor(() => {
      const calls = vi.mocked(fetchHadiths).mock.calls
      const last = calls[calls.length - 1]!
      expect(last[2]).toMatchObject({ narrator: undefined })
    })
    expect(
      screen.getByRole("combobox", { name: /filter by isnad narrator/i }),
    ).toBeInTheDocument()
  })
})
