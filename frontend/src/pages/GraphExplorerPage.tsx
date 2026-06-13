import { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  fetchGraphNetwork,
  fetchNarrators,
  fetchNarrator,
  fetchNarratorChains,
} from '../api/client'
import ForceGraph from '../components/ForceGraph'
import { communityColor } from '../components/ForceGraph'
import type { GraphNode, GraphEdge, Narrator, ChainSummary } from '../types/api'

const NODE_LIMIT = 5000
const SUGGESTED_NARRATORS = ['Abu Hurayra', 'al-Zuhri', 'Malik ibn Anas', 'Aisha bint Abi Bakr']

type LayoutMode = 'force' | 'hierarchy' | 'radial'

export default function GraphExplorerPage() {
  // --- State ---
  const [searchInput, setSearchInput] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  const [selectedNarratorId, setSelectedNarratorId] = useState<string | null>(null)
  const [depth, setDepth] = useState(1)
  const [allNodes, setAllNodes] = useState<GraphNode[]>([])
  const [allEdges, setAllEdges] = useState<GraphEdge[]>([])
  const [detailOpen, setDetailOpen] = useState(false)
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null)
  const [legendOpen, setLegendOpen] = useState(false)
  const [filterOpen, setFilterOpen] = useState(false)
  const [highlightedChainNodeIds, setHighlightedChainNodeIds] = useState<Set<string> | null>(null)
  const [layoutMode, setLayoutMode] = useState<LayoutMode>('force')
  const containerRef = useRef<HTMLDivElement | null>(null)
  const searchRef = useRef<HTMLInputElement | null>(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })

  // --- Data queries ---
  const { data: searchResults } = useQuery({
    queryKey: ['narrator-search', searchInput],
    queryFn: () => fetchNarrators(1, 10, searchInput),
    enabled: searchInput.length > 1,
  })

  const { data: networkData, isLoading } = useQuery({
    queryKey: ['graph-network', selectedNarratorId, depth],
    queryFn: () => fetchGraphNetwork(selectedNarratorId!, depth),
    enabled: selectedNarratorId != null,
  })

  const { data: narratorDetail } = useQuery({
    queryKey: ['narrator-detail', selectedNarratorId],
    queryFn: () => fetchNarrator(selectedNarratorId!),
    enabled: selectedNarratorId != null && detailOpen,
  })

  const { data: chainsData } = useQuery({
    queryKey: ['narrator-chains', selectedNarratorId],
    queryFn: () => fetchNarratorChains(selectedNarratorId!),
    enabled: selectedNarratorId != null && detailOpen,
  })

  // --- Merge network data (progressive subgraph loading) ---
  useEffect(() => {
    if (!networkData) return
    setAllNodes((prev) => {
      const existing = new Map(prev.map((n) => [n.id, n]))
      for (const n of networkData.nodes) {
        existing.set(n.id, n)
      }
      return Array.from(existing.values())
    })
    setAllEdges((prev) => {
      const existing = new Set(prev.map((e) => `${e.source}->${e.target}:${e.relationship}`))
      const merged = [...prev]
      for (const e of networkData.edges) {
        const key = `${e.source}->${e.target}:${e.relationship}`
        if (!existing.has(key)) {
          merged.push(e)
          existing.add(key)
        }
      }
      return merged
    })
  }, [networkData])

  // --- Resize observer ---
  useEffect(() => {
    if (!containerRef.current) return
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) {
        setDimensions({
          width: entry.contentRect.width,
          height: Math.max(400, entry.contentRect.height),
        })
      }
    })
    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  // --- Keyboard shortcuts ---
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        if (highlightedChainNodeIds) {
          setHighlightedChainNodeIds(null)
        } else if (detailOpen) {
          setDetailOpen(false)
        } else if (searchOpen) {
          setSearchOpen(false)
        }
      }
      if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
        const target = e.target as HTMLElement
        if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA') {
          e.preventDefault()
          searchRef.current?.focus()
        }
      }
      if (e.key === '?') {
        const target = e.target as HTMLElement
        if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA') {
          setLegendOpen((v) => !v)
        }
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [highlightedChainNodeIds, detailOpen, searchOpen])

  // --- Unique communities in current data ---
  const communities = useMemo(() => {
    const seen = new Map<number, number>()
    for (const n of allNodes) {
      if (n.community_id != null) {
        seen.set(n.community_id, (seen.get(n.community_id) ?? 0) + 1)
      }
    }
    return Array.from(seen.entries())
      .filter(([, count]) => count >= 3)
      .sort((a, b) => b[1] - a[1])
  }, [allNodes])

  // --- Handlers ---
  const handleNodeClick = useCallback((nodeId: string) => {
    setSelectedNarratorId(nodeId)
    setDetailOpen(true)
    setHighlightedChainNodeIds(null)
  }, [])

  const handleNodeHover = useCallback((node: GraphNode | null) => {
    setHoveredNode(node)
  }, [])

  const handleReset = useCallback(() => {
    setAllNodes([])
    setAllEdges([])
    setSelectedNarratorId(null)
    setSearchInput('')
    setDetailOpen(false)
    setHighlightedChainNodeIds(null)
    setHoveredNode(null)
  }, [])

  const handleSelectSearch = useCallback(
    (narratorId: string) => {
      setSelectedNarratorId(narratorId)
      setSearchInput('')
      setSearchOpen(false)
      setDetailOpen(true)
    },
    [],
  )

  const handleSuggestedSearch = useCallback((name: string) => {
    setSearchInput(name)
    setSearchOpen(true)
    searchRef.current?.focus()
  }, [])

  const overLimit = allNodes.length > NODE_LIMIT

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 64px)' }}>
      {/* --- TOOLBAR --- */}
      <div
        className="flex flex-wrap items-center gap-3 px-4 py-2"
        style={{
          borderBottom: '1px solid var(--color-border)',
          background: 'var(--color-card)',
        }}
      >
        {/* Search */}
        <div className="relative w-[300px]">
          <input
            ref={searchRef}
            type="text"
            placeholder="Search narrator..."
            value={searchInput}
            onChange={(e) => {
              setSearchInput(e.target.value)
              setSearchOpen(true)
            }}
            onFocus={() => setSearchOpen(true)}
            className="form-input w-full pr-8"
            aria-label="Search for a narrator"
          />
          {searchInput && (
            <button
              onClick={() => {
                setSearchInput('')
                setSearchOpen(false)
              }}
              className="absolute right-2 top-1/2 -translate-y-1/2 cursor-pointer border-none"
              style={{
                background: 'none',
                fontSize: '1rem',
                color: 'var(--color-muted-foreground)',
              }}
              aria-label="Clear search"
            >
              x
            </button>
          )}

          {searchOpen && searchInput && searchResults && searchResults.items.length > 0 && (
            <div
              className="search-dropdown absolute top-full left-0 right-0 max-h-60 overflow-y-auto rounded-md"
              style={{
                zIndex: 'var(--z-dropdown)',
                background: 'var(--color-card)',
                border: '1px solid var(--color-border)',
                boxShadow: 'var(--shadow-md)',
              }}
            >
              {searchResults.items.map((n) => (
                <div
                  key={n.id}
                  onClick={() => handleSelectSearch(n.id)}
                  className="search-dropdown-item flex cursor-pointer items-center justify-between px-3 py-2"
                >
                  <span>{n.name_en}</span>
                  <span dir="rtl" lang="ar" className="muted-text" style={{ fontSize: '0.875rem' }}>
                    {n.name_ar}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Depth control */}
        <div className="flex items-center gap-1">
          <span className="muted-text" style={{ fontSize: '0.875rem' }}>Depth:</span>
          {[1, 2, 3].map((d) => (
            <button
              key={d}
              onClick={() => setDepth(d)}
              title="Number of transmission steps from selected narrator"
              className="cursor-pointer rounded-sm px-2.5 py-1"
              style={{
                border: '1px solid var(--color-border)',
                background:
                  d === depth ? 'var(--color-primary, oklch(0.55 0.14 45))' : 'transparent',
                color: d === depth ? 'var(--color-primary-foreground)' : 'inherit',
                fontWeight: d === depth ? 600 : 400,
                fontSize: '0.875rem',
              }}
            >
              {d}
            </button>
          ))}
        </div>

        {/* Layout toggle */}
        <div className="flex items-center gap-1">
          <span className="muted-text" style={{ fontSize: '0.875rem' }}>Layout:</span>
          {(['force', 'hierarchy', 'radial'] as LayoutMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => setLayoutMode(mode)}
              className="cursor-pointer rounded-sm px-2 py-1 capitalize"
              style={{
                border: '1px solid var(--color-border)',
                background:
                  mode === layoutMode
                    ? 'var(--color-primary, oklch(0.55 0.14 45))'
                    : 'transparent',
                color: mode === layoutMode ? 'var(--color-primary-foreground)' : 'inherit',
                fontSize: '0.8rem',
              }}
            >
              {mode}
            </button>
          ))}
        </div>

        {/* Filter button */}
        <button
          onClick={() => setFilterOpen(!filterOpen)}
          className="btn"
          style={{ fontSize: '0.875rem' }}
        >
          Filters
        </button>

        {/* Reset */}
        <button onClick={handleReset} className="btn" style={{ fontSize: '0.875rem' }}>
          Reset
        </button>

        {/* Legend toggle */}
        <button
          onClick={() => setLegendOpen(!legendOpen)}
          className="btn"
          style={{ fontSize: '0.875rem' }}
        >
          Legend
        </button>

        {/* Chain highlight clear */}
        {highlightedChainNodeIds && (
          <button
            onClick={() => setHighlightedChainNodeIds(null)}
            className="btn"
            style={{ fontSize: '0.875rem', color: 'var(--color-primary)' }}
          >
            Clear highlight
          </button>
        )}

        {isLoading && <span className="muted-text" style={{ fontSize: '0.875rem' }}>Loading...</span>}
      </div>

      {/* --- Node limit warning --- */}
      {overLimit && (
        <div
          className="px-4 py-2"
          style={{
            background: 'var(--color-warning)',
            color: 'var(--color-warning-foreground)',
            fontSize: '0.875rem',
          }}
        >
          This query returned {allNodes.length} nodes. For performance, results are capped at{' '}
          {NODE_LIMIT}. Apply filters or reduce depth.
          <button
            onClick={() => setFilterOpen(true)}
            className="btn ml-2"
            style={{ fontSize: '0.8rem' }}
          >
            Open Filters
          </button>
        </div>
      )}

      {/* --- MAIN CONTENT --- */}
      <div className="relative flex flex-1 overflow-hidden">
        {/* --- GRAPH CANVAS --- */}
        <div
          ref={containerRef}
          className="relative flex-1"
          style={{ background: 'var(--color-background)' }}
          role="application"
          aria-label="Narrator transmission network graph"
        >
          {allNodes.length > 0 ? (
            <ForceGraph
              nodes={allNodes}
              edges={allEdges}
              selectedNodeId={selectedNarratorId}
              highlightedChainNodeIds={highlightedChainNodeIds}
              onNodeClick={handleNodeClick}
              onNodeHover={handleNodeHover}
              width={dimensions.width}
              height={dimensions.height}
            />
          ) : (
            <div className="empty-state h-full">
              <div className="empty-state-icon">
                <svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                  <circle cx="16" cy="16" r="4" />
                  <circle cx="48" cy="16" r="4" />
                  <circle cx="32" cy="48" r="4" />
                  <circle cx="48" cy="48" r="4" />
                  <line x1="20" y1="16" x2="44" y2="16" strokeDasharray="4 3" />
                  <line x1="18" y1="20" x2="30" y2="44" strokeDasharray="4 3" />
                  <line x1="34" y1="48" x2="44" y2="48" strokeDasharray="4 3" />
                </svg>
              </div>
              <div className="empty-state-heading">No graph data</div>
              <div className="empty-state-body">
                Search for a narrator to explore the transmission network.
              </div>
              <p className="mt-4" style={{ fontSize: 'var(--text-sm)' }}>
                Try:{' '}
                {SUGGESTED_NARRATORS.map((name, i) => (
                  <span key={name}>
                    {i > 0 && ', '}
                    <button
                      onClick={() => handleSuggestedSearch(name)}
                      className="link-primary cursor-pointer border-none p-0 underline"
                      style={{
                        background: 'none',
                        font: 'inherit',
                      }}
                    >
                      {name}
                    </button>
                  </span>
                ))}
              </p>
            </div>
          )}

          {/* Hover tooltip */}
          {hoveredNode && (
            <div
              className="pointer-events-none absolute top-3 left-3 z-10 max-w-[280px] rounded-md px-3 py-2"
              style={{
                background: 'var(--color-card)',
                border: '1px solid var(--color-border)',
                fontSize: '0.8rem',
                boxShadow: 'var(--shadow-md)',
              }}
            >
              <div className="font-semibold">
                {hoveredNode.name_en || hoveredNode.label}
              </div>
              {hoveredNode.name_ar && (
                <div dir="rtl" lang="ar" style={{ fontSize: '0.85rem' }}>
                  {hoveredNode.name_ar}
                </div>
              )}
              {hoveredNode.generation && <div>Gen: {hoveredNode.generation}</div>}
              {hoveredNode.death_year_ah != null && <div>d. {hoveredNode.death_year_ah} AH</div>}
              <div>
                {(hoveredNode.in_degree ?? 0) + (hoveredNode.out_degree ?? 0)} connections
              </div>
              {hoveredNode.trustworthiness_consensus && (
                <div>Trustworthiness: {hoveredNode.trustworthiness_consensus}</div>
              )}
            </div>
          )}

          {/* Legend panel */}
          {legendOpen && (
            <div
              className="absolute top-3 z-10 w-[220px] rounded-md p-3"
              style={{
                right: detailOpen ? 340 : 12,
                background: 'var(--color-card)',
                border: '1px solid var(--color-border)',
                fontSize: '0.8rem',
                boxShadow: 'var(--shadow-md)',
              }}
            >
              <div className="mb-2 font-semibold">Legend</div>

              <div className="mb-2">
                <div className="mb-1 font-medium">Node size: degree</div>
                <div className="flex items-center gap-2">
                  <svg width="8" height="8">
                    <circle cx="4" cy="4" r="3" fill="var(--color-muted-foreground)" />
                  </svg>
                  1-5
                  <svg width="16" height="16">
                    <circle cx="8" cy="8" r="6" fill="var(--color-muted-foreground)" />
                  </svg>
                  6-20
                  <svg width="24" height="24">
                    <circle cx="12" cy="12" r="9" fill="var(--color-muted-foreground)" />
                  </svg>
                  21+
                </div>
              </div>

              <div className="mb-2">
                <div className="mb-1 font-medium">
                  Node color: community
                </div>
                {communities.map(([cid, count]) => (
                  <div key={cid} className="flex items-center gap-1">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{ background: communityColor(cid) }}
                    />
                    Community {cid} ({count})
                  </div>
                ))}
              </div>

              <div className="mb-2">
                <div className="mb-1 font-medium">
                  Edge: transmission direction
                </div>
                <div>Solid = TRANSMITTED_TO</div>
                <div>Dashed = STUDIED_UNDER</div>
                <div>Thickness = frequency</div>
              </div>
            </div>
          )}

          {/* Zoom controls */}
          {allNodes.length > 0 && (
            <div className="absolute bottom-10 left-3 z-10 flex flex-col gap-0.5">
              {[
                { label: '+', title: 'Zoom in' },
                { label: '-', title: 'Zoom out' },
              ].map((btn) => (
                <button
                  key={btn.label}
                  title={btn.title}
                  aria-label={btn.title}
                  className="h-8 w-8 cursor-pointer rounded-sm"
                  style={{
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-card)',
                    fontSize: '1rem',
                  }}
                >
                  {btn.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* --- DETAIL PANEL --- */}
        {detailOpen && selectedNarratorId && (
          <div
            className="w-[320px] shrink-0 overflow-y-auto p-4"
            style={{
              borderLeft: '1px solid var(--color-border)',
              background: 'var(--color-card)',
            }}
          >
            <div className="mb-4 flex items-center justify-between">
              <span
                className="uppercase"
                style={{
                  fontSize: '0.75rem',
                  letterSpacing: '0.05em',
                  color: 'var(--color-muted-foreground)',
                }}
              >
                Narrator
              </span>
              <button
                onClick={() => setDetailOpen(false)}
                className="cursor-pointer border-none"
                style={{
                  background: 'none',
                  fontSize: '1rem',
                  color: 'var(--color-muted-foreground)',
                }}
                aria-label="Close detail panel"
              >
                x
              </button>
            </div>

            {narratorDetail ? (
              <NarratorDetailPanel
                narrator={narratorDetail}
                chains={chainsData?.chains ?? []}
                chainsTotal={chainsData?.total ?? 0}
                onChainSelect={(_chain) => {
                  // For now, highlight is a stub — full chain path requires backend chain-path API
                  setHighlightedChainNodeIds(null)
                }}
              />
            ) : (
              <p className="muted-text" style={{ fontSize: '0.875rem' }}>Loading details...</p>
            )}
          </div>
        )}
      </div>

      {/* --- STATUS BAR --- */}
      <div
        className="flex gap-6 px-4 py-1"
        style={{
          borderTop: '1px solid var(--color-border)',
          fontSize: '0.75rem',
          color: 'var(--color-muted-foreground)',
          background: 'var(--color-card)',
        }}
      >
        <span>
          {allNodes.length} nodes, {allEdges.length} edges
        </span>
        {communities.length > 0 && (
          <span>
            {communities.length} communit{communities.length === 1 ? 'y' : 'ies'}
          </span>
        )}
      </div>
    </div>
  )
}

// --- Narrator Detail Panel sub-component ---

function NarratorDetailPanel({
  narrator,
  chains,
  chainsTotal,
  onChainSelect,
}: {
  narrator: Narrator
  chains: ChainSummary[]
  chainsTotal: number
  onChainSelect: (chain: ChainSummary) => void
}) {
  return (
    <div>
      {/* Names */}
      {narrator.name_ar && (
        <div
          dir="rtl"
          lang="ar"
          className="mb-1"
          style={{
            fontSize: '1.25rem',
            fontFamily: "var(--font-arabic, 'Noto Naskh Arabic', serif)",
          }}
        >
          {narrator.name_ar}
        </div>
      )}
      <div className="mb-4 font-medium" style={{ fontSize: '1rem' }}>
        {narrator.name_en}
      </div>

      {/* Metadata */}
      <div className="mb-4" style={{ fontSize: '0.85rem', lineHeight: 1.6 }}>
        {narrator.kunya && (
          <div>
            <span className="muted-text">Kunya:</span> {narrator.kunya}
          </div>
        )}
        {narrator.nisba && (
          <div>
            <span className="muted-text">Nisba:</span> {narrator.nisba}
          </div>
        )}
        {narrator.generation && (
          <div>
            <span className="muted-text">Generation:</span> {narrator.generation}
          </div>
        )}
        <div>
          <span className="muted-text">Birth:</span>{' '}
          {narrator.birth_year_ah != null ? `${narrator.birth_year_ah} AH` : '\u2014'}
          {' | '}
          <span className="muted-text">Death:</span>{' '}
          {narrator.death_year_ah != null ? `${narrator.death_year_ah} AH` : '\u2014'}
        </div>
        {narrator.sect_affiliation && (
          <div>
            <span className="muted-text">Sect:</span> {narrator.sect_affiliation}
          </div>
        )}
        {narrator.trustworthiness_consensus && (
          <div>
            <span className="muted-text">Trustworthiness:</span>{' '}
            {narrator.trustworthiness_consensus}
          </div>
        )}
      </div>

      {/* Network statistics */}
      <div
        className="mb-4 pt-3"
        style={{
          borderTop: '1px solid var(--color-border)',
        }}
      >
        <div
          className="mb-2 uppercase"
          style={{
            fontSize: '0.75rem',
            letterSpacing: '0.05em',
            color: 'var(--color-muted-foreground)',
          }}
        >
          Network Statistics
        </div>
        <div style={{ fontSize: '0.85rem', lineHeight: 1.6 }}>
          <div>
            <span className="muted-text">Teachers (in):</span> {narrator.in_degree ?? '\u2014'}
          </div>
          <div>
            <span className="muted-text">Students (out):</span>{' '}
            {narrator.out_degree ?? '\u2014'}
          </div>
          {narrator.betweenness_centrality != null && (
            <div>
              <span className="muted-text">Betweenness:</span>{' '}
              {narrator.betweenness_centrality.toFixed(4)}
            </div>
          )}
          {narrator.pagerank != null && (
            <div>
              <span className="muted-text">PageRank:</span> {narrator.pagerank.toFixed(4)}
            </div>
          )}
          {narrator.community_id != null && (
            <div className="flex items-center gap-1">
              <span className="muted-text">Community:</span> {narrator.community_id}
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ background: communityColor(narrator.community_id) }}
              />
            </div>
          )}
        </div>
      </div>

      {/* Chains */}
      <div
        className="mb-4 pt-3"
        style={{
          borderTop: '1px solid var(--color-border)',
        }}
      >
        <div className="mb-2 flex items-center justify-between">
          <span
            className="uppercase"
            style={{
              fontSize: '0.75rem',
              letterSpacing: '0.05em',
              color: 'var(--color-muted-foreground)',
            }}
          >
            Chains ({chainsTotal} total)
          </span>
        </div>
        <div className="max-h-[200px] overflow-y-auto">
          {chains.length === 0 && (
            <div className="muted-text" style={{ fontSize: '0.85rem' }}>No chains found.</div>
          )}
          {chains.map((c) => (
            <div
              key={c.chain_id}
              onClick={() => onChainSelect(c)}
              className="cursor-pointer px-0 py-1.5"
              style={{
                borderBottom: '1px solid var(--color-border)',
                fontSize: '0.8rem',
              }}
            >
              <div className="font-medium">
                {c.grade && <span className="muted-text">[{c.grade}]</span>}{' '}
                {c.matn_en || c.hadith_id}
              </div>
              {c.matn_ar && (
                <div
                  dir="rtl"
                  lang="ar"
                  className="muted-text max-w-full truncate"
                  style={{ fontSize: '0.75rem' }}
                >
                  {c.matn_ar}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Link to full profile */}
      <Link
        to={`/narrators/${narrator.id}`}
        className="block rounded-md p-2 text-center no-underline"
        style={{
          color: 'var(--color-primary)',
          fontSize: '0.85rem',
          border: '1px solid var(--color-border)',
        }}
      >
        View Full Profile
      </Link>
    </div>
  )
}
