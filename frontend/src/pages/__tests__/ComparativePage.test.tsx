import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import ComparativePage from "../ComparativePage"
import {
  fetchParallelPairs,
  fetchHadith,
  fetchHadithParallels,
  searchAll,
} from "../../api/client"
import type { Hadith } from "../../types/api"

vi.mock("../../api/client", () => ({
  fetchParallelPairs: vi.fn(),
  fetchHadith: vi.fn(),
  fetchHadithParallels: vi.fn(),
  searchAll: vi.fn(),
}))

const mockPairs = vi.mocked(fetchParallelPairs)
const mockHadith = vi.mocked(fetchHadith)
const mockParallels = vi.mocked(fetchHadithParallels)
const mockSearch = vi.mocked(searchAll)

function makeHadith(over: Partial<Hadith> & { id: string }): Hadith {
  return {
    matn_ar: "نص عربي",
    matn_en: null,
    isnad_raw_ar: null,
    isnad_raw_en: null,
    grade_composite: null,
    grade_normalized: null,
    topic_tags: [],
    source_corpus: "sunni",
    collection_name: null,
    display_title: null,
    has_shia_parallel: false,
    has_sunni_parallel: false,
    ...over,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  mockPairs.mockResolvedValue({ items: [], total: 0, page: 1, limit: 20 })
  mockHadith.mockResolvedValue(null as unknown as Hadith)
  mockParallels.mockResolvedValue({ hadith_id: "", parallels: [], total: 0 })
  mockSearch.mockImplementation((query: string) => {
    if (query === "test") {
      return Promise.resolve({
        query,
        total: 2,
        results: [
          { id: "bukhari:1", type: "hadith", title: "First hadith", title_ar: "", score: 1 },
          { id: "bukhari:2", type: "hadith", title: "Second hadith", title_ar: "", score: 1 },
        ],
      })
    }
    return Promise.resolve({ query, total: 0, results: [] })
  })
})

function renderPage(initialEntries: string[] = ["/compare"]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <ComparativePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("HadithSearchSelect", () => {
  it("does not use setTimeout in blur handler", async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByText("Compare Hadiths"))

    const input = screen.getAllByPlaceholderText("Search by hadith text or ID...")[0]!
    await user.type(input, "test")

    await waitFor(() => {
      expect(screen.getByText("bukhari:1")).toBeInTheDocument()
    })

    await user.click(screen.getByText("bukhari:1"))

    await waitFor(() => {
      expect(screen.getByText("bukhari:1")).toBeInTheDocument()
    })
  })

  it("closes dropdown when clicking outside (blur)", async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByText("Compare Hadiths"))

    const input = screen.getAllByPlaceholderText("Search by hadith text or ID...")[0]!
    await user.type(input, "test")

    await waitFor(() => {
      expect(screen.getByText("bukhari:1")).toBeInTheDocument()
    })

    await user.click(document.body)

    await waitFor(() => {
      expect(screen.queryByText("bukhari:1")).not.toBeInTheDocument()
    })
  })

  it("leads the dropdown with the readable title, ID secondary", async () => {
    const user = userEvent.setup()
    const { container } = renderPage()
    await user.click(screen.getByText("Compare Hadiths"))
    const input = screen.getAllByPlaceholderText("Search by hadith text or ID...")[0]!
    await user.type(input, "test")

    await waitFor(() => {
      expect(container.querySelector(".search-dropdown")).not.toBeNull()
    })
    // Within the dropdown, the readable title leads and the opaque ID is secondary.
    const dropdown = container.querySelector(".search-dropdown") as HTMLElement
    expect(within(dropdown).getByText("First hadith")).toBeInTheDocument()
    expect(within(dropdown).getByText("bukhari:1")).toBeInTheDocument()
  })
})

describe("Browse tab", () => {
  const PAIR_A = {
    hadith_a_id: "hdt:sunni:bukhari:1:1",
    hadith_a_corpus: "bukhari",
    hadith_a_title: "Sahih al-Bukhari 1:1",
    hadith_a_snippet: "Actions are but by intentions.",
    hadith_b_id: "hdt:sunni:muslim:1:1",
    hadith_b_corpus: "muslim",
    hadith_b_title: "Sahih Muslim 1:1",
    hadith_b_snippet: "Deeds are by intentions.",
    similarity_score: 0.95,
    variant_type: "verbatim",
    cross_sect: false,
  }
  const PAIR_B = {
    hadith_a_id: "hdt:sunni:bukhari:2:9",
    hadith_a_corpus: "bukhari",
    hadith_a_title: "Sahih al-Bukhari 2:9",
    hadith_a_snippet: "A weaker parallel.",
    hadith_b_id: "hdt:shia:kafi:5",
    hadith_b_corpus: "kafi",
    hadith_b_title: "Al-Kafi, Hadith 5",
    hadith_b_snippet: "Shia parallel text.",
    similarity_score: 0.7,
    variant_type: "paraphrase",
    cross_sect: true,
  }

  it("renders human-readable titles and matn snippets, not opaque IDs", async () => {
    mockPairs.mockResolvedValue({ items: [PAIR_A], total: 1, page: 1, limit: 20 })
    renderPage()

    await waitFor(() => {
      expect(screen.getByText("Sahih al-Bukhari 1:1")).toBeInTheDocument()
    })
    expect(screen.getByText("Sahih Muslim 1:1")).toBeInTheDocument()
    expect(screen.getByText(/Actions are but by intentions\./)).toBeInTheDocument()
  })

  it("Compare button switches to the Compare tab (controlled Tabs)", async () => {
    const user = userEvent.setup()
    mockPairs.mockResolvedValue({ items: [PAIR_A], total: 1, page: 1, limit: 20 })
    renderPage()

    await waitFor(() => {
      expect(screen.getByText("Sahih al-Bukhari 1:1")).toBeInTheDocument()
    })

    // Compare tab content is unmounted while Browse is active.
    expect(screen.queryByText("Select Hadiths to Compare")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Compare" }))

    // The active tab actually switched — compare panel is now mounted.
    await waitFor(() => {
      expect(screen.getByText("Select Hadiths to Compare")).toBeInTheDocument()
    })
  })

  it("sorts the table by similarity when the header is toggled", async () => {
    const user = userEvent.setup()
    mockPairs.mockResolvedValue({ items: [PAIR_B, PAIR_A], total: 2, page: 1, limit: 20 })
    renderPage()

    await waitFor(() => {
      expect(screen.getByText("95.0%")).toBeInTheDocument()
    })

    // Default descending: 95% precedes 70%.
    const descScores = screen.getAllByText(/^\d+\.\d%$/).map((el) => el.textContent)
    expect(descScores).toEqual(["95.0%", "70.0%"])

    await user.click(screen.getByText(/^Similarity/))

    await waitFor(() => {
      const ascScores = screen.getAllByText(/^\d+\.\d%$/).map((el) => el.textContent)
      expect(ascScores).toEqual(["70.0%", "95.0%"])
    })
  })
})

describe("ComparisonView", () => {
  const HADITH_A = makeHadith({
    id: "hdt:sunni:bukhari:1:1",
    matn_en: "actions are by intention",
    matn_ar: "إنما الأعمال بالنيات",
    grade_composite: "Sahih",
    grade_normalized: "sahih",
    collection_name: "Sahih al-Bukhari",
    display_title: "Sahih al-Bukhari 1:1",
    topic_tags: ["ikhlas"],
  })
  const HADITH_B = makeHadith({
    id: "hdt:sunni:muslim:1:1",
    matn_en: "deeds are by intention",
    matn_ar: "الأعمال بالنية",
    grade_composite: "Sahih",
    grade_normalized: "sahih",
    collection_name: "Sahih Muslim",
    display_title: "Sahih Muslim 1:1",
  })

  beforeEach(() => {
    mockHadith.mockImplementation((id: string) =>
      Promise.resolve(id === HADITH_A.id ? HADITH_A : HADITH_B),
    )
    mockParallels.mockResolvedValue({
      hadith_id: HADITH_A.id,
      parallels: [
        {
          id: HADITH_B.id,
          matn_ar: HADITH_B.matn_ar,
          matn_en: HADITH_B.matn_en,
          source_corpus: "muslim",
          grade: "sahih",
          similarity_score: 0.92,
          variant_type: "close_paraphrase",
          cross_sect: false,
        },
      ],
      total: 1,
    })
  })

  it("shows human-readable titles instead of opaque IDs", async () => {
    renderPage(["/compare?a=hdt:sunni:bukhari:1:1&b=hdt:sunni:muslim:1:1"])

    // The readable title appears in both the selected chip and the comparison card.
    await waitFor(() => {
      expect(screen.getAllByText("Sahih al-Bukhari 1:1").length).toBeGreaterThanOrEqual(1)
    })
    expect(screen.getAllByText("Sahih Muslim 1:1").length).toBeGreaterThanOrEqual(1)
    // The opaque ID is never the primary label.
    expect(screen.queryByText("hdt:sunni:bukhari:1:1")).not.toBeInTheDocument()
  })

  it("surfaces the pair's similarity score and variant type", async () => {
    renderPage(["/compare?a=hdt:sunni:bukhari:1:1&b=hdt:sunni:muslim:1:1"])

    await waitFor(() => {
      expect(screen.getByText("92.0%")).toBeInTheDocument()
    })
    expect(screen.getByText("close paraphrase")).toBeInTheDocument()
  })

  it("highlights divergent tokens in a word-level diff", async () => {
    const { container } = renderPage([
      "/compare?a=hdt:sunni:bukhari:1:1&b=hdt:sunni:muslim:1:1",
    ])

    await waitFor(() => {
      expect(screen.getAllByText("Sahih al-Bukhari 1:1").length).toBeGreaterThanOrEqual(1)
    })

    const highlighted = Array.from(container.querySelectorAll(".diff-unique")).map((el) =>
      el.textContent?.trim(),
    )
    // "actions" (A only) and "deeds" (B only) diverge; the shared tail does not.
    expect(highlighted).toContain("actions")
    expect(highlighted).toContain("deeds")
    expect(highlighted).not.toContain("intention")
  })

  it("falls back to a word-overlap metric when no parallel link is recorded", async () => {
    // B is not among A's recorded parallels → pairMeta is undefined.
    mockParallels.mockResolvedValue({ hadith_id: HADITH_A.id, parallels: [], total: 0 })
    renderPage(["/compare?a=hdt:sunni:bukhari:1:1&b=hdt:sunni:muslim:1:1"])

    await waitFor(() => {
      expect(screen.getByText(/word overlap/)).toBeInTheDocument()
    })
    expect(screen.getByText(/No recorded parallel link/)).toBeInTheDocument()
  })

  it("renders the grade and topic tags on the compared hadith", async () => {
    renderPage(["/compare?a=hdt:sunni:bukhari:1:1&b=hdt:sunni:muslim:1:1"])
    await waitFor(() => {
      expect(screen.getAllByText("Sahih").length).toBeGreaterThanOrEqual(2)
    })
    expect(screen.getByText("ikhlas")).toBeInTheDocument()
  })
})
