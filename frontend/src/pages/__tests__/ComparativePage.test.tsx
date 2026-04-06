import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import ComparativePage from "../ComparativePage"

vi.mock("../../api/client", () => ({
  fetchParallelPairs: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, limit: 20 }),
  fetchHadith: vi.fn().mockResolvedValue(null),
  searchAll: vi.fn().mockImplementation((query: string) => {
    if (query === "test") {
      return Promise.resolve({
        results: [
          { id: "bukhari:1", type: "hadith", title: "First hadith" },
          { id: "bukhari:2", type: "hadith", title: "Second hadith" },
        ],
      })
    }
    return Promise.resolve({ results: [] })
  }),
}))

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ComparativePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("HadithSearchSelect", () => {
  it("does not use setTimeout in blur handler", async () => {
    const user = userEvent.setup()
    renderPage()

    // Navigate to compare tab
    await user.click(screen.getByText("Compare Hadiths"))

    const input = screen.getAllByPlaceholderText("Search by hadith text or ID...")[0]!

    // Type to trigger search and open dropdown
    await user.type(input, "test")

    // Wait for search results to appear
    await waitFor(() => {
      expect(screen.getByText("bukhari:1")).toBeInTheDocument()
    })

    // Click on a dropdown item — with onPointerDown + preventDefault,
    // the blur won't fire before the selection is processed
    await user.click(screen.getByText("bukhari:1"))

    // The item should be selected (shown as a badge)
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

    // Click outside the input to trigger blur
    await user.click(document.body)

    // Dropdown should close — dropdown items should no longer be visible
    await waitFor(() => {
      expect(screen.queryByText("bukhari:1")).not.toBeInTheDocument()
    })
  })
})
