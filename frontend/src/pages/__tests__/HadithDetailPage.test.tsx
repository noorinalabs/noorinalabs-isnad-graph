import { render, screen, waitFor, fireEvent } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import HadithDetailPage from "../HadithDetailPage"
import {
  fetchHadith,
  fetchHadithParallels,
  fetchHadithChain,
  fetchHadithDating,
} from "../../api/client"
import type {
  Hadith,
  ParallelsResponse,
  ChainVisualization,
  HadithDatingResponse,
} from "../../types/api"

vi.mock("../../api/client", () => ({
  fetchHadith: vi.fn(),
  fetchHadithParallels: vi.fn(),
  fetchHadithChain: vi.fn(),
  fetchHadithDating: vi.fn(),
}))

const EMPTY_CHAIN: ChainVisualization = {
  hadith_id: "bukhari:1",
  nodes: [],
  edges: [],
}

const INSUFFICIENT_DATING: HadithDatingResponse = {
  hadith_id: "bukhari:1",
  terminus_post_quem_ah: null,
  terminus_ante_quem_ah: null,
  chain_span_ah: null,
  confidence: "insufficient_data",
  chain_narrator_count: 0,
  dated_narrator_count: 0,
  earliest_narrator: null,
  latest_narrator: null,
  assumed_lifespan_ah: 80,
  note: "Insufficient data: this hadith has no reconstructable isnad chain.",
}

const RESOLVED_DATING: HadithDatingResponse = {
  hadith_id: "bukhari:1",
  terminus_post_quem_ah: 58,
  terminus_ante_quem_ah: 179,
  chain_span_ah: 121,
  confidence: "high",
  chain_narrator_count: 3,
  dated_narrator_count: 3,
  earliest_narrator: {
    narrator_id: "nar:abu-hurayra",
    name_ar: null,
    name_en: "Abu Hurayra",
    birth_year_ah: null,
    death_year_ah: 58,
    window_start_ah: -22,
    window_end_ah: 58,
    estimated: true,
  },
  latest_narrator: {
    narrator_id: "nar:malik",
    name_ar: null,
    name_en: "Malik ibn Anas",
    birth_year_ah: null,
    death_year_ah: 179,
    window_start_ah: 99,
    window_end_ah: 179,
    estimated: true,
  },
  assumed_lifespan_ah: 80,
  note: "Chain resolves to AH 58-179 (high confidence) from 3 of 3 dated narrators.",
}

function makeHadith(overrides: Partial<Hadith> = {}): Hadith {
  return {
    id: "bukhari:1",
    matn_ar: "إنما الأعمال بالنيات",
    matn_en: "Actions are but by intentions",
    isnad_raw_ar: null,
    isnad_raw_en: null,
    grade_composite: "Sahih - Authentic",
    grade_normalized: "sahih",
    topic_tags: ["intention", "worship"],
    source_corpus: "Sahih al-Bukhari",
    collection_name: "Bukhari",
    display_title: "Bukhari 1",
    has_sunni_parallel: true,
    has_shia_parallel: false,
    ...overrides,
  }
}

function renderAt(path = "/hadiths/bukhari:1") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/hadiths/:id" element={<HadithDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("HadithDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default: no chain edges. Tests that exercise the chain override this.
    vi.mocked(fetchHadithChain).mockResolvedValue(EMPTY_CHAIN)
    // Default: insufficient dating. Tests that exercise dating override this.
    vi.mocked(fetchHadithDating).mockResolvedValue(INSUFFICIENT_DATING)
    // Clipboard polyfill — jsdom omits navigator.clipboard.writeText
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    })
  })

  describe("loading + error + not-found branches", () => {
    it("renders the skeleton while loading", () => {
      vi.mocked(fetchHadith).mockImplementation(() => new Promise(() => {}))
      vi.mocked(fetchHadithParallels).mockImplementation(() => new Promise(() => {}))
      const { container } = renderAt()
      expect(container.querySelector(".animate-pulse")).not.toBeNull()
    })

    it("shows the error message when fetchHadith fails", async () => {
      vi.mocked(fetchHadith).mockRejectedValue(new Error("hadith-404"))
      vi.mocked(fetchHadithParallels).mockResolvedValue({
        hadith_id: "bukhari:1",
        parallels: [],
        total: 0,
      })
      renderAt()
      await waitFor(() => {
        expect(screen.getByText(/Error: hadith-404/)).toBeInTheDocument()
      })
    })

    it("shows 'Hadith not found.' when data is null/undefined", async () => {
      vi.mocked(fetchHadith).mockResolvedValue(null as never)
      vi.mocked(fetchHadithParallels).mockResolvedValue({
        hadith_id: "bukhari:1",
        parallels: [],
        total: 0,
      })
      renderAt()
      await waitFor(() => {
        expect(screen.getByText("Hadith not found.")).toBeInTheDocument()
      })
    })
  })

  describe("rendering with full data", () => {
    it("renders Arabic matn, English matn, grade badge, and metadata", async () => {
      vi.mocked(fetchHadith).mockResolvedValue(makeHadith())
      vi.mocked(fetchHadithParallels).mockResolvedValue({
        hadith_id: "bukhari:1",
        parallels: [],
        total: 0,
      })
      renderAt()

      await screen.findByText("Bukhari 1", { selector: "h2" })
      expect(screen.getByText("إنما الأعمال بالنيات")).toBeInTheDocument()
      expect(
        screen.getByText("Actions are but by intentions"),
      ).toBeInTheDocument()
      // Raw free-text grade is shown verbatim, coloured from the normalized token.
      const badge = screen.getByText("Sahih - Authentic", { selector: "span" })
      expect(badge).toBeInTheDocument()
      expect(badge).toHaveClass("text-sahih")
      // Metadata fields
      expect(screen.getByText("Collection")).toBeInTheDocument()
      expect(screen.getByText("Bukhari")).toBeInTheDocument()
      expect(screen.getByText("Source Corpus")).toBeInTheDocument()
      expect(screen.getByText("Sunni parallel")).toBeInTheDocument()
      expect(screen.queryByText("Shia parallel")).not.toBeInTheDocument()
    })

    it("renders the isnad-raw prefix in front of the Arabic matn when present", async () => {
      vi.mocked(fetchHadith).mockResolvedValue(
        makeHadith({
          isnad_raw_ar: "حدثنا أبو هريرة",
          isnad_raw_en: "Narrated by Abu Hurayra",
        }),
      )
      vi.mocked(fetchHadithParallels).mockResolvedValue({
        hadith_id: "bukhari:1",
        parallels: [],
        total: 0,
      })
      renderAt()

      await screen.findByText("Bukhari 1", { selector: "h2" })
      expect(screen.getByText(/حدثنا أبو هريرة/)).toBeInTheDocument()
      expect(screen.getByText(/Narrated by Abu Hurayra/)).toBeInTheDocument()
    })

    it("renders topic badges that link to /search", async () => {
      vi.mocked(fetchHadith).mockResolvedValue(makeHadith())
      vi.mocked(fetchHadithParallels).mockResolvedValue({
        hadith_id: "bukhari:1",
        parallels: [],
        total: 0,
      })
      renderAt()

      await screen.findByText("Topics")
      const intentionLink = screen.getByRole("link", { name: /intention/i })
      expect(intentionLink).toHaveAttribute(
        "href",
        "/search?q=intention",
      )
    })

    it("renders parallel hadith with similarity scores and a Compare link", async () => {
      vi.mocked(fetchHadith).mockResolvedValue(makeHadith())
      const parallels: ParallelsResponse = {
        hadith_id: "bukhari:1",
        total: 2,
        parallels: [
          {
            id: "muslim:1",
            matn_ar: "إنما الأعمال بالنيات (مسلم)",
            matn_en: "Muslim's version",
            source_corpus: "Sahih Muslim",
            grade: "Sahih",
            similarity_score: 0.95,
            variant_type: "verbatim",
            cross_sect: false,
          },
          {
            id: "kafi:1",
            matn_ar: "نسخة كافي",
            matn_en: null,
            source_corpus: "al-Kafi",
            grade: null,
            similarity_score: 0.72,
            variant_type: "thematic",
            cross_sect: true,
          },
        ],
      }
      vi.mocked(fetchHadithParallels).mockResolvedValue(parallels)
      renderAt()

      await screen.findByText(/Parallel Hadith \(2 found\)/)
      expect(screen.getByText("Sahih Muslim")).toBeInTheDocument()
      expect(screen.getByText("Similarity: 95%")).toBeInTheDocument()
      expect(screen.getByText("al-Kafi")).toBeInTheDocument()
      expect(screen.getByText("Similarity: 72%")).toBeInTheDocument()
      expect(screen.getByText("Cross-sect")).toBeInTheDocument()
      // Find the inner "Compare" link by exact name match — outer parallel
      // cards are anchors too (the entire card is clickable), so the inner
      // Compare link needs to be matched by exact name.
      const compareLinks = screen.getAllByRole("link", { name: "Compare" })
      expect(compareLinks).toHaveLength(2)
      expect(compareLinks[0]).toHaveAttribute(
        "href",
        "/compare?a=bukhari:1&b=muslim:1",
      )
      expect(compareLinks[1]).toHaveAttribute(
        "href",
        "/compare?a=bukhari:1&b=kafi:1",
      )
    })
  })

  describe("isnad chain (#1032)", () => {
    it("renders the chain narrators in transmission order from the chain edges", async () => {
      vi.mocked(fetchHadith).mockResolvedValue(makeHadith())
      vi.mocked(fetchHadithParallels).mockResolvedValue({
        hadith_id: "bukhari:1",
        parallels: [],
        total: 0,
      })
      const chain: ChainVisualization = {
        hadith_id: "bukhari:1",
        nodes: [
          {
            id: "nar:umar",
            label: "Umar",
            name_ar: "عمر بن الخطاب",
            name_en: "Umar ibn al-Khattab",
            type: "narrator",
            generation: "companion",
            community_id: null,
            in_degree: null,
            out_degree: null,
            betweenness_centrality: null,
            pagerank: null,
            sect_affiliation: null,
            trustworthiness_consensus: null,
            death_year_ah: null,
            birth_year_ah: null,
            kunya: null,
            nisba: null,
            over_merged: false,
            over_merge_note: null,
          },
          {
            id: "nar:zuhri",
            label: "al-Zuhri",
            name_ar: "محمد بن مسلم الزهري",
            name_en: "Ibn Shihab al-Zuhri",
            type: "narrator",
            generation: "tabi_tabiin",
            community_id: null,
            in_degree: null,
            out_degree: null,
            betweenness_centrality: null,
            pagerank: null,
            sect_affiliation: null,
            trustworthiness_consensus: null,
            death_year_ah: null,
            birth_year_ah: null,
            kunya: null,
            nisba: null,
            over_merged: false,
            over_merge_note: null,
          },
        ],
        edges: [
          {
            source: "nar:umar",
            target: "nar:zuhri",
            relationship: "TRANSMITTED_TO",
            weight: 1,
            position: 0,
          },
        ],
      }
      vi.mocked(fetchHadithChain).mockResolvedValue(chain)
      renderAt()

      const chainList = await screen.findByRole("list", {
        name: /isnad chain in transmission order/i,
      })
      expect(chainList).toBeInTheDocument()
      expect(screen.getByText("عمر بن الخطاب")).toBeInTheDocument()
      expect(screen.getByText("محمد بن مسلم الزهري")).toBeInTheDocument()
      // Narrators link to their detail pages
      const umarLink = screen.getByRole("link", { name: /Umar ibn al-Khattab/i })
      expect(umarLink).toHaveAttribute("href", "/narrators/nar%3Aumar")
    })

    it("shows an empty-state message when the hadith has no chain edges", async () => {
      vi.mocked(fetchHadith).mockResolvedValue(makeHadith())
      vi.mocked(fetchHadithParallels).mockResolvedValue({
        hadith_id: "bukhari:1",
        parallels: [],
        total: 0,
      })
      // EMPTY_CHAIN is the beforeEach default
      renderAt()

      await screen.findByText("Bukhari 1", { selector: "h2" })
      expect(
        screen.getByText(/No isnad chain available for this hadith yet/i),
      ).toBeInTheDocument()
    })
  })

  describe("copy-to-clipboard buttons", () => {
    it("copies the citation when the Copy-citation button is clicked", async () => {
      vi.mocked(fetchHadith).mockResolvedValue(makeHadith())
      vi.mocked(fetchHadithParallels).mockResolvedValue({
        hadith_id: "bukhari:1",
        parallels: [],
        total: 0,
      })
      renderAt()

      const copyBtn = await screen.findByRole("button", {
        name: "Copy citation",
      })
      fireEvent.click(copyBtn)

      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
          expect.stringContaining("Bukhari 1, Hadith bukhari:1"),
        )
      })
      // Button label flips to "Copied!" once the async writeText resolves
      await screen.findByRole("button", { name: "Copied!" })
    })

    it("copies the Arabic matn when the Copy-Arabic button is clicked", async () => {
      vi.mocked(fetchHadith).mockResolvedValue(makeHadith())
      vi.mocked(fetchHadithParallels).mockResolvedValue({
        hadith_id: "bukhari:1",
        parallels: [],
        total: 0,
      })
      renderAt()

      const btn = await screen.findByRole("button", {
        name: "Copy Arabic text",
      })
      fireEvent.click(btn)
      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
          "إنما الأعمال بالنيات",
        )
      })
    })

    it("hides the Copy-translation button when matn_en is null", async () => {
      vi.mocked(fetchHadith).mockResolvedValue(makeHadith({ matn_en: null }))
      vi.mocked(fetchHadithParallels).mockResolvedValue({
        hadith_id: "bukhari:1",
        parallels: [],
        total: 0,
      })
      renderAt()

      await screen.findByRole("button", { name: "Copy citation" })
      expect(
        screen.queryByRole("button", { name: "Copy translation" }),
      ).not.toBeInTheDocument()
    })
  })

  describe("share button", () => {
    it("falls back to clipboard when navigator.share is undefined", async () => {
      vi.mocked(fetchHadith).mockResolvedValue(makeHadith())
      vi.mocked(fetchHadithParallels).mockResolvedValue({
        hadith_id: "bukhari:1",
        parallels: [],
        total: 0,
      })

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (navigator as any).share

      renderAt()
      const shareBtn = await screen.findByRole("button", { name: "Share" })
      fireEvent.click(shareBtn)

      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalled()
      })
      const calls = vi.mocked(navigator.clipboard.writeText).mock.calls
      expect(calls.length).toBeGreaterThan(0)
      const arg = calls[0]![0]
      expect(arg).toMatch(/^http/)
    })

    it("uses navigator.share when present", async () => {
      const shareSpy = vi.fn().mockResolvedValue(undefined)
      Object.defineProperty(navigator, "share", {
        configurable: true,
        value: shareSpy,
      })
      vi.mocked(fetchHadith).mockResolvedValue(makeHadith())
      vi.mocked(fetchHadithParallels).mockResolvedValue({
        hadith_id: "bukhari:1",
        parallels: [],
        total: 0,
      })

      renderAt()
      const shareBtn = await screen.findByRole("button", { name: "Share" })
      fireEvent.click(shareBtn)
      await waitFor(() => {
        expect(shareSpy).toHaveBeenCalledTimes(1)
      })
      // Clipboard NOT used when share resolves successfully
      expect(navigator.clipboard.writeText).not.toHaveBeenCalled()
    })

    it("falls back to clipboard when navigator.share rejects (user cancel)", async () => {
      Object.defineProperty(navigator, "share", {
        configurable: true,
        value: vi.fn().mockRejectedValue(new Error("AbortError")),
      })
      vi.mocked(fetchHadith).mockResolvedValue(makeHadith())
      vi.mocked(fetchHadithParallels).mockResolvedValue({
        hadith_id: "bukhari:1",
        parallels: [],
        total: 0,
      })

      renderAt()
      const shareBtn = await screen.findByRole("button", { name: "Share" })
      fireEvent.click(shareBtn)
      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalled()
      })
    })
  })
  describe("chain-derived dating (ig#1042)", () => {
    it("renders the derived terminus window and confidence when dated", async () => {
      vi.mocked(fetchHadith).mockResolvedValue(makeHadith())
      vi.mocked(fetchHadithParallels).mockResolvedValue({
        hadith_id: "bukhari:1",
        parallels: [],
        total: 0,
      })
      vi.mocked(fetchHadithDating).mockResolvedValue(RESOLVED_DATING)
      renderAt()

      await screen.findByText("Chain-Derived Dating")
      // The AH range is surfaced (post-quem 58 .. ante-quem 179).
      expect(screen.getByText("AH 58–179")).toBeInTheDocument()
      expect(screen.getByText("Terminus post quem (earliest)")).toBeInTheDocument()
      expect(screen.getByText("Terminus ante quem (latest)")).toBeInTheDocument()
      // Span + confidence.
      expect(screen.getByText("121 years")).toBeInTheDocument()
      expect(screen.getByText("High")).toBeInTheDocument()
    })

    it("shows the insufficient-data note without a 500 when the chain is undated", async () => {
      vi.mocked(fetchHadith).mockResolvedValue(makeHadith())
      vi.mocked(fetchHadithParallels).mockResolvedValue({
        hadith_id: "bukhari:1",
        parallels: [],
        total: 0,
      })
      // INSUFFICIENT_DATING is the beforeEach default.
      renderAt()

      await screen.findByText("Chain-Derived Dating")
      expect(
        screen.getByText(/Insufficient data: this hadith has no reconstructable isnad chain/i),
      ).toBeInTheDocument()
      // The AH-range line is absent for the insufficient branch.
      expect(screen.queryByText(/AH \d+–\d+/)).not.toBeInTheDocument()
    })
  })

})
