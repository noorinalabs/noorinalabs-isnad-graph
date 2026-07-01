import { render, screen } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import TimelinePage from "../TimelinePage"
import {
  fetchTimeline,
  fetchTimelineRange,
  fetchCollections,
  fetchNarratorTimeline,
} from "../../api/client"
import type { NarratorTimelineEntry } from "../../types/api"

vi.mock("../../api/client", () => ({
  fetchTimeline: vi.fn(),
  fetchTimelineRange: vi.fn(),
  fetchCollections: vi.fn(),
  fetchNarratorTimeline: vi.fn(),
}))

const mockTimeline = vi.mocked(fetchTimeline)
const mockRange = vi.mocked(fetchTimelineRange)
const mockCollections = vi.mocked(fetchCollections)
const mockNarrators = vi.mocked(fetchNarratorTimeline)

function makeNarrator(over: Partial<NarratorTimelineEntry> & { narrator_id: string }): NarratorTimelineEntry {
  return {
    name_ar: null,
    name_en: null,
    birth_year_ah: null,
    death_year_ah: null,
    window_start_ah: 0,
    window_end_ah: 100,
    birth_date_precision: null,
    death_date_precision: null,
    tabaqat_class: null,
    estimated: true,
    ...over,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  mockRange.mockResolvedValue({ min_year_ah: 0, max_year_ah: 300 })
  mockTimeline.mockResolvedValue({ entries: [], total: 0 })
  mockCollections.mockResolvedValue({ items: [], total: 0, page: 1, limit: 100 })
  mockNarrators.mockResolvedValue({ entries: [], total: 0 })
})

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/timeline"]}>
        <TimelinePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("TimelinePage narrator lifespan/ṭabaqa lanes", () => {
  it("renders a lane per dated narrator returned by the endpoint", async () => {
    mockNarrators.mockResolvedValue({
      entries: [
        makeNarrator({
          narrator_id: "malik",
          name_en: "Malik ibn Anas",
          name_ar: "مالك بن أنس",
          birth_year_ah: 93,
          death_year_ah: 179,
          window_start_ah: 93,
          window_end_ah: 179,
          tabaqat_class: "7",
          estimated: false,
        }),
        makeNarrator({
          narrator_id: "shafii",
          name_en: "al-Shafiʿi",
          birth_year_ah: null,
          death_year_ah: 204,
          window_start_ah: 124,
          window_end_ah: 204,
          tabaqat_class: "9",
          estimated: true,
        }),
      ],
      total: 2,
    })

    renderPage()

    // Both narrator names are drawn as lane labels.
    expect(await screen.findByText("Malik ibn Anas")).toBeInTheDocument()
    expect(await screen.findByText("al-Shafiʿi")).toBeInTheDocument()
    // The estimated narrator's lane carries the "estimated" marker. (findAllByText
    // because the SVG <text> marker is matched both directly and via its wrapping
    // <g> lane group under Testing Library's ancestor-text aggregation.)
    expect((await screen.findAllByText(/estimated/i)).length).toBeGreaterThan(0)
    // The lanes section title is present (heading role, to avoid matching the
    // events empty-state prose that also mentions "narrator lifespans").
    expect(
      screen.getByRole("heading", { name: /Narrator Lifespans/i }),
    ).toBeInTheDocument()
  })

  it("shows the empty message when the endpoint returns no dated narrators", async () => {
    mockNarrators.mockResolvedValue({ entries: [], total: 0 })

    renderPage()

    expect(await screen.findByText(/No dated narrators/i)).toBeInTheDocument()
  })
})
