/**
 * GraphExplorerPage test — D3 / canvas mocking strategy
 * ------------------------------------------------------
 * GraphExplorerPage renders a `ForceGraph` component that wraps `react-force-graph-2d`,
 * which itself drives an HTMLCanvasElement via D3 force-simulation. jsdom does NOT
 * implement HTMLCanvasElement.getContext (returns null), so the real component would
 * throw or warn when rendered under Vitest.
 *
 * Strategy: stub the entire `ForceGraph` component at the module boundary using
 * `vi.mock`. The stub renders a deterministic `<div role="application">` with the
 * incoming nodes/edges as data-* attributes, which gives us:
 *   - zero canvas calls (no jsdom workaround needed)
 *   - assertable props (nodes/edges/selectedNodeId visible in DOM)
 *   - exercise of every code path in GraphExplorerPage that is NOT inside the
 *     canvas drawing routine
 *
 * `communityColor` is re-exported from the real module so the toolbar's legend code
 * (which calls it directly) keeps working. Tests that need to assert against the
 * actual canvas drawing of D3 belong in Playwright (golden path / accessibility),
 * not Vitest — see frontend/tests/e2e/graph.spec.ts.
 *
 * `fetchNarrators` is called from two places with different signatures: the
 * default-graph SEED query (`fetchNarrators(1, 100)` — no `q`) and the search-box
 * query (`fetchNarrators(1, 10, q)` — with `q`). The mock below is argument-aware
 * so the two are controlled independently via the module-scoped `seedItems` /
 * `searchItems` arrays — seed defaults to empty so search-focused tests are not
 * perturbed by the auto-seed (#1031).
 *
 * The narrator-search dropdown, depth/layout toggles, reset behavior, ID-seeded
 * suggestion chips, default auto-seed, and detail-panel open/close are all covered here.
 */
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import GraphExplorerPage from "../GraphExplorerPage"
import {
  fetchGraphNetwork,
  fetchNarrators,
  fetchNarrator,
  fetchNarratorChains,
} from "../../api/client"
import type {
  GraphNode,
  GraphEdge,
  Narrator,
  NarratorNetworkResponse,
  PaginatedResponse,
} from "../../types/api"

vi.mock("../../api/client", () => ({
  fetchGraphNetwork: vi.fn(),
  fetchNarrators: vi.fn(),
  fetchNarrator: vi.fn(),
  fetchNarratorChains: vi.fn(),
}))

vi.mock("../../components/ForceGraph", () => ({
  default: (props: {
    nodes: GraphNode[]
    edges: GraphEdge[]
    selectedNodeId: string | null
    layoutMode?: string
    nodeLayerRank?: Map<string, number> | null
    layerCount?: number
  }) => (
    <div
      data-testid="force-graph-stub"
      data-node-count={props.nodes.length}
      data-edge-count={props.edges.length}
      data-selected={props.selectedNodeId ?? ""}
      data-layout={props.layoutMode ?? ""}
      data-layer-count={props.layerCount ?? 0}
      data-node-ranks={
        props.nodeLayerRank
          ? [...props.nodeLayerRank.entries()]
              .map(([id, rank]) => `${id}:${rank}`)
              .join(",")
          : ""
      }
    >
      ForceGraph stub
    </div>
  ),
  // The toolbar legend imports `communityColor` from this module — stub it as a
  // deterministic function so assertions about color swatches don't rely on D3.
  communityColor: (cid: number) => `hsl(${cid * 30}, 60%, 50%)`,
}))

function makeNarrator(overrides: Partial<Narrator> = {}): Narrator {
  return {
    id: "n1",
    name_ar: "أبو هريرة",
    name_en: "Abu Hurayra",
    kunya: null,
    nisba: null,
    laqab: null,
    birth_year_ah: 19,
    death_year_ah: 59,
    generation: "Companion",
    gender: "M",
    sect_affiliation: "Sunni",
    trustworthiness_consensus: "Thiqa",
    aliases: [],
    betweenness_centrality: 0.5,
    in_degree: 10,
    out_degree: 20,
    pagerank: 0.01,
    community_id: 1,
    ...overrides,
  }
}

function makeNode(overrides: Partial<GraphNode> = {}): GraphNode {
  return {
    id: "n1",
    label: "Abu Hurayra",
    name_ar: "أبو هريرة",
    name_en: "Abu Hurayra",
    type: "narrator",
    generation: "Companion",
    community_id: 1,
    in_degree: 10,
    out_degree: 20,
    betweenness_centrality: 0.5,
    pagerank: 0.01,
    sect_affiliation: "Sunni",
    trustworthiness_consensus: "Thiqa",
    death_year_ah: 59,
    birth_year_ah: 19,
    kunya: null,
    nisba: null,
    ...overrides,
  }
}

function page(items: Narrator[]): PaginatedResponse<Narrator> {
  return { items, total: items.length, page: 1, limit: Math.max(items.length, 10) }
}

// Independently-controlled fixtures for the two fetchNarrators call sites.
let seedItems: Narrator[] = []
let searchItems: Narrator[] = []

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <GraphExplorerPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  seedItems = []
  searchItems = []
  // Argument-aware: the seed query passes no `q`; the search query passes one.
  vi.mocked(fetchNarrators).mockImplementation((_page, _limit, q) =>
    Promise.resolve(page(q ? searchItems : seedItems)),
  )
  // ResizeObserver isn't in jsdom — minimal stub so the resize-effect doesn't throw.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(globalThis as any).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
})

describe("GraphExplorerPage — empty state (no seed data)", () => {
  it("renders the empty-state message when there is no seed data", () => {
    renderPage()
    expect(screen.getByText("No graph data")).toBeInTheDocument()
    expect(
      screen.getByText(/Search for a narrator to explore/i),
    ).toBeInTheDocument()
  })

  it("renders no suggestion chips when seed data is unavailable", () => {
    renderPage()
    expect(screen.queryByText(/^Try:/)).not.toBeInTheDocument()
  })

  it("renders 0 nodes / 0 edges in the status bar by default", () => {
    renderPage()
    expect(screen.getByText("0 nodes, 0 edges")).toBeInTheDocument()
  })

  it("does NOT render the ForceGraph stub when there are no nodes", () => {
    renderPage()
    expect(screen.queryByTestId("force-graph-stub")).not.toBeInTheDocument()
  })
})

describe("GraphExplorerPage — default auto-seed (#1031)", () => {
  it("seeds the highest-degree narrator's network on load with no user interaction", async () => {
    // Two candidates; the second is the higher-degree hub and must be chosen.
    seedItems = [
      makeNarrator({ id: "low", name_en: "Low Degree", in_degree: 1, out_degree: 1 }),
      makeNarrator({ id: "hub", name_en: "Big Hub", in_degree: 100, out_degree: 200 }),
    ]
    vi.mocked(fetchGraphNetwork).mockResolvedValue({
      narrator_id: "hub",
      nodes: [makeNode({ id: "hub" }), makeNode({ id: "n2", label: "n2" })],
      edges: [
        { source: "hub", target: "n2", relationship: "TRANSMITTED_TO", weight: 1 },
      ],
      teachers: 1,
      students: 1,
    })

    renderPage()

    const stub = await screen.findByTestId("force-graph-stub")
    expect(stub).toHaveAttribute("data-selected", "hub")
    expect(stub).toHaveAttribute("data-node-count", "2")
    // The ego-network query was issued for the highest-degree narrator.
    expect(fetchGraphNetwork).toHaveBeenCalledWith("hub", 1)
  })
})

describe("GraphExplorerPage — ID-seeded suggestion chips (#1031)", () => {
  it("renders one-click chips from real seed narrators", async () => {
    seedItems = [
      makeNarrator({ id: "low", name_en: "Low Degree", in_degree: 1, out_degree: 0 }),
      makeNarrator({ id: "hub", name_en: "Big Hub", in_degree: 100, out_degree: 50 }),
    ]
    // Seed network is empty so the empty state (and its chips) stays rendered.
    vi.mocked(fetchGraphNetwork).mockResolvedValue({
      narrator_id: "hub",
      nodes: [],
      edges: [],
      teachers: 0,
      students: 0,
    })

    renderPage()

    const hubChip = await screen.findByRole("button", { name: "Big Hub" })
    const lowChip = screen.getByRole("button", { name: "Low Degree" })
    expect(hubChip).toBeInTheDocument()
    expect(lowChip).toBeInTheDocument()
  })

  it("selects the narrator by id in a single click (no name-search round-trip)", async () => {
    const user = userEvent.setup()
    seedItems = [
      makeNarrator({ id: "hub", name_en: "Big Hub", in_degree: 100, out_degree: 50 }),
      makeNarrator({ id: "other", name_en: "Other Narrator", in_degree: 5, out_degree: 5 }),
    ]
    vi.mocked(fetchGraphNetwork).mockResolvedValue({
      narrator_id: "hub",
      nodes: [],
      edges: [],
      teachers: 0,
      students: 0,
    })

    renderPage()

    const otherChip = await screen.findByRole("button", { name: "Other Narrator" })
    await user.click(otherChip)

    // One click issues the network query for that narrator's id directly.
    await waitFor(() => {
      expect(fetchGraphNetwork).toHaveBeenCalledWith("other", 1)
    })
    // The search box was not used to resolve the chip.
    const input = screen.getByLabelText("Search for a narrator") as HTMLInputElement
    expect(input.value).toBe("")
  })
})

describe("GraphExplorerPage — toolbar controls", () => {
  it("highlights the active depth button when clicked", async () => {
    const user = userEvent.setup()
    renderPage()
    // Default depth is 1 — button "1" should have a non-transparent background.
    // Click "2" — it becomes the active depth.
    await user.click(screen.getByRole("button", { name: "2" }))
    // Visual state assertion: the active button has fontWeight 600. Inspect
    // via getComputedStyle/inline style.
    const btn2 = screen.getByRole("button", { name: "2" })
    expect(btn2).toHaveStyle({ fontWeight: "600" })
  })

  it("switches layout mode when a layout button is clicked", async () => {
    const user = userEvent.setup()
    renderPage()
    const force = screen.getByRole("button", { name: /^force$/i })
    const radial = screen.getByRole("button", { name: /radial/i })
    // Default layout is 'force' — the active button uses the primary background.
    // Capture initial inline-background of force vs radial.
    const forceBgBefore = force.style.background
    const radialBgBefore = radial.style.background
    expect(forceBgBefore).not.toBe(radialBgBefore)

    await user.click(radial)
    // After clicking radial, the two backgrounds should have swapped:
    // radial now has the active (primary) background, force has transparent.
    expect(radial.style.background).toBe(forceBgBefore)
    expect(force.style.background).toBe(radialBgBefore)
  })

  it("opens the legend panel when 'Legend' is clicked", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole("button", { name: "Legend" }))
    expect(screen.getByText("Node size: degree")).toBeInTheDocument()
    expect(screen.getByText("Node color: community")).toBeInTheDocument()
    expect(screen.getByText("Edge: transmission direction")).toBeInTheDocument()
  })

  it("opens the search dropdown when typing", async () => {
    const user = userEvent.setup()
    // Use a name that's NOT a seed chip, so the dropdown match is unambiguous.
    searchItems = [makeNarrator({ id: "n1", name_en: "Sufyan al-Thawri" })]

    renderPage()
    const input = screen.getByLabelText("Search for a narrator")
    await user.type(input, "Sufy")
    await waitFor(() => {
      expect(fetchNarrators).toHaveBeenCalledWith(1, 10, "Sufy")
    })
    expect(await screen.findByText("Sufyan al-Thawri")).toBeInTheDocument()
  })
})

describe("GraphExplorerPage — network data integration", () => {
  it("renders the ForceGraph stub when network data is loaded via search selection", async () => {
    const user = userEvent.setup()
    searchItems = [makeNarrator({ id: "n1", name_en: "Sufyan al-Thawri" })]

    const network: NarratorNetworkResponse = {
      narrator_id: "n1",
      nodes: [makeNode({ id: "n1" }), makeNode({ id: "n2", label: "n2" })],
      edges: [
        { source: "n1", target: "n2", relationship: "TRANSMITTED_TO", weight: 1 },
      ],
      teachers: 1,
      students: 1,
    }
    vi.mocked(fetchGraphNetwork).mockResolvedValue(network)
    vi.mocked(fetchNarrator).mockResolvedValue(makeNarrator({ id: "n1" }))
    vi.mocked(fetchNarratorChains).mockResolvedValue({
      narrator_id: "n1",
      chains: [],
      total: 0,
    })

    renderPage()
    const input = screen.getByLabelText("Search for a narrator")
    await user.type(input, "Sufy")

    const dropdownItem = await screen.findByText("Sufyan al-Thawri")
    await user.click(dropdownItem)

    const stub = await screen.findByTestId("force-graph-stub")
    expect(stub).toHaveAttribute("data-node-count", "2")
    expect(stub).toHaveAttribute("data-edge-count", "1")
    expect(stub).toHaveAttribute("data-selected", "n1")

    // Status bar reflects the loaded counts
    expect(screen.getByText("2 nodes, 1 edges")).toBeInTheDocument()
  })

  it("opens the detail panel and renders narrator metadata after selection", async () => {
    const user = userEvent.setup()
    searchItems = [makeNarrator({ id: "n1", name_en: "Sufyan al-Thawri" })]
    vi.mocked(fetchGraphNetwork).mockResolvedValue({
      narrator_id: "n1",
      nodes: [makeNode({ id: "n1" })],
      edges: [],
      teachers: 0,
      students: 0,
    })
    vi.mocked(fetchNarrator).mockResolvedValue(
      makeNarrator({
        id: "n1",
        name_en: "Sufyan al-Thawri",
        kunya: "Abu Abdallah",
        nisba: "al-Thawri",
      }),
    )
    vi.mocked(fetchNarratorChains).mockResolvedValue({
      narrator_id: "n1",
      chains: [],
      total: 0,
    })

    renderPage()
    await user.type(
      screen.getByLabelText("Search for a narrator"),
      "Sufy",
    )
    const dropdownItem = await screen.findByText("Sufyan al-Thawri")
    await user.click(dropdownItem)

    // Wait for the detail panel to render the narrator info
    await screen.findByText("Network Statistics")
    expect(screen.getByText("al-Thawri")).toBeInTheDocument()
    expect(screen.getByText(/Companion/)).toBeInTheDocument()
    // "View Full Profile" link is rendered with the narrator id
    expect(
      screen.getByRole("link", { name: /View Full Profile/i }),
    ).toHaveAttribute("href", "/narrators/n1")
  })

  it("closes the detail panel when the close button is clicked", async () => {
    const user = userEvent.setup()
    searchItems = [makeNarrator({ id: "n1", name_en: "Sufyan al-Thawri" })]
    vi.mocked(fetchGraphNetwork).mockResolvedValue({
      narrator_id: "n1",
      nodes: [makeNode({ id: "n1" })],
      edges: [],
      teachers: 0,
      students: 0,
    })
    vi.mocked(fetchNarrator).mockResolvedValue(makeNarrator({ id: "n1" }))
    vi.mocked(fetchNarratorChains).mockResolvedValue({
      narrator_id: "n1",
      chains: [],
      total: 0,
    })

    renderPage()
    await user.type(
      screen.getByLabelText("Search for a narrator"),
      "Sufy",
    )
    const dropdownItem = await screen.findByText("Sufyan al-Thawri")
    await user.click(dropdownItem)

    await screen.findByText("Network Statistics")
    await user.click(
      screen.getByRole("button", { name: "Close detail panel" }),
    )
    await waitFor(() => {
      expect(screen.queryByText("Network Statistics")).not.toBeInTheDocument()
    })
  })

  it("resets all state when Reset is clicked", async () => {
    const user = userEvent.setup()
    searchItems = [makeNarrator({ id: "n1", name_en: "Sufyan al-Thawri" })]
    vi.mocked(fetchGraphNetwork).mockResolvedValue({
      narrator_id: "n1",
      nodes: [makeNode({ id: "n1" })],
      edges: [],
      teachers: 0,
      students: 0,
    })
    vi.mocked(fetchNarrator).mockResolvedValue(makeNarrator({ id: "n1" }))
    vi.mocked(fetchNarratorChains).mockResolvedValue({
      narrator_id: "n1",
      chains: [],
      total: 0,
    })

    renderPage()
    await user.type(
      screen.getByLabelText("Search for a narrator"),
      "Sufy",
    )
    const dropdownItem = await screen.findByText("Sufyan al-Thawri")
    await user.click(dropdownItem)

    await screen.findByTestId("force-graph-stub")
    await user.click(screen.getByRole("button", { name: "Reset" }))

    // After reset, the empty-state is back and the stub is gone
    await waitFor(() => {
      expect(screen.queryByTestId("force-graph-stub")).not.toBeInTheDocument()
    })
    expect(screen.getByText("No graph data")).toBeInTheDocument()
    expect(screen.getByText("0 nodes, 0 edges")).toBeInTheDocument()
  })

  it("does not re-seed the default graph after an explicit Reset", async () => {
    const user = userEvent.setup()
    // Seed data is present — but a Reset must leave the canvas blank, not
    // immediately repopulate it with the default subgraph (#1031).
    seedItems = [makeNarrator({ id: "hub", name_en: "Big Hub", in_degree: 100, out_degree: 50 })]
    vi.mocked(fetchGraphNetwork).mockResolvedValue({
      narrator_id: "hub",
      nodes: [makeNode({ id: "hub" })],
      edges: [],
      teachers: 0,
      students: 0,
    })
    vi.mocked(fetchNarrator).mockResolvedValue(makeNarrator({ id: "hub" }))
    vi.mocked(fetchNarratorChains).mockResolvedValue({
      narrator_id: "hub",
      chains: [],
      total: 0,
    })

    renderPage()
    // Auto-seed renders the default graph first.
    await screen.findByTestId("force-graph-stub")

    await user.click(screen.getByRole("button", { name: "Reset" }))

    await waitFor(() => {
      expect(screen.queryByTestId("force-graph-stub")).not.toBeInTheDocument()
    })
    // Stays blank — the auto-seed effect must not fire again.
    expect(screen.getByText("No graph data")).toBeInTheDocument()
    expect(screen.getByText("0 nodes, 0 edges")).toBeInTheDocument()
  })
})

describe("GraphExplorerPage — over-limit warning", () => {
  it("renders the over-limit banner when more than NODE_LIMIT nodes are loaded", async () => {
    const user = userEvent.setup()
    searchItems = [makeNarrator({ id: "big", name_en: "Big Network" })]
    // 5001 nodes — exceeds the page's NODE_LIMIT (5000)
    const bigNodes = Array.from({ length: 5001 }, (_, i) =>
      makeNode({ id: `n${i}` }),
    )
    vi.mocked(fetchGraphNetwork).mockResolvedValue({
      narrator_id: "big",
      nodes: bigNodes,
      edges: [],
      teachers: 0,
      students: 0,
    })
    vi.mocked(fetchNarrator).mockResolvedValue(makeNarrator({ id: "big" }))
    vi.mocked(fetchNarratorChains).mockResolvedValue({
      narrator_id: "big",
      chains: [],
      total: 0,
    })

    renderPage()
    await user.type(
      screen.getByLabelText("Search for a narrator"),
      "Bi",
    )
    const dropdownItem = await screen.findByText("Big Network")
    await user.click(dropdownItem)

    const warning = await screen.findByText(
      /This query returned 5001 nodes/i,
    )
    expect(warning).toBeInTheDocument()
    expect(within(warning.parentElement!).getByRole("button", {
      name: "Open Filters",
    })).toBeInTheDocument()
  })
})

describe("GraphExplorerPage — ṭabaqa generation layering (ig#1043)", () => {
  it("offers a Ṭabaqa layout toggle", () => {
    renderPage()
    expect(
      screen.getByRole("button", { name: /abaqa/i }),
    ).toBeInTheDocument()
  })

  it("layers loaded nodes into chronological generation bands and passes ranks to the graph", async () => {
    const user = userEvent.setup()
    searchItems = [makeNarrator({ id: "root", name_en: "Root Narrator" })]
    vi.mocked(fetchGraphNetwork).mockResolvedValue({
      narrator_id: "root",
      // Deliberately out of chronological order and mixing an unknown generation.
      nodes: [
        makeNode({ id: "later", generation: "later" }),
        makeNode({ id: "sahabi", generation: "sahabi" }),
        makeNode({ id: "tabii", generation: "tabii" }),
        makeNode({ id: "mystery", generation: "not-a-real-tabaqa" }),
      ],
      edges: [],
      teachers: 0,
      students: 0,
    })
    vi.mocked(fetchNarrator).mockResolvedValue(makeNarrator({ id: "root" }))
    vi.mocked(fetchNarratorChains).mockResolvedValue({
      narrator_id: "root",
      chains: [],
      total: 0,
    })

    renderPage()
    await user.type(screen.getByLabelText("Search for a narrator"), "Root")
    const dropdownItem = await screen.findByText("Root Narrator")
    await user.click(dropdownItem)

    const stub = await screen.findByTestId("force-graph-stub")

    // Switching to the Ṭabaqa layout wires the mode + band ranks into the graph.
    await user.click(screen.getByRole("button", { name: /abaqa/i }))
    await waitFor(() => {
      expect(stub).toHaveAttribute("data-layout", "tabaqa")
    })

    // Four bands present: sahabi(0) < tabii(1) < later(2) < unknown(3), earliest
    // generation first, unmapped generation collected into the trailing band.
    expect(stub).toHaveAttribute("data-layer-count", "4")
    const ranks = Object.fromEntries(
      (stub.getAttribute("data-node-ranks") ?? "")
        .split(",")
        .map((pair) => pair.split(":")),
    )
    expect(ranks["sahabi"]).toBe("0")
    expect(ranks["tabii"]).toBe("1")
    expect(ranks["later"]).toBe("2")
    // Unknown/unmapped generation is placed last, after every known band.
    expect(ranks["mystery"]).toBe("3")
  })

  it("annotates the canvas with the generation bands in chronological order", async () => {
    const user = userEvent.setup()
    searchItems = [makeNarrator({ id: "root", name_en: "Root Narrator" })]
    vi.mocked(fetchGraphNetwork).mockResolvedValue({
      narrator_id: "root",
      nodes: [
        makeNode({ id: "sahabi", generation: "sahabi" }),
        makeNode({ id: "tabii", generation: "tabii" }),
      ],
      edges: [],
      teachers: 0,
      students: 0,
    })
    vi.mocked(fetchNarrator).mockResolvedValue(makeNarrator({ id: "root" }))
    vi.mocked(fetchNarratorChains).mockResolvedValue({
      narrator_id: "root",
      chains: [],
      total: 0,
    })

    renderPage()
    await user.type(screen.getByLabelText("Search for a narrator"), "Root")
    await user.click(await screen.findByText("Root Narrator"))
    await screen.findByTestId("force-graph-stub")

    // No band overlay until the ṭabaqa layout is active.
    expect(screen.queryByTestId("tabaqa-bands")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /abaqa/i }))
    const overlay = await screen.findByTestId("tabaqa-bands")
    // Earliest generation (Companions) is listed above the next (Successors).
    const companions = within(overlay).getByText("Companions")
    const successors = within(overlay).getByText("Successors")
    expect(
      companions.compareDocumentPosition(successors) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })
})
