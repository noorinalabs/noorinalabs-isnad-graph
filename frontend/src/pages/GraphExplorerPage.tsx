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
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)' }}>
      {/* --- TOOLBAR --- */}
      <div
        style={{
          padding: '0.5rem 1rem',
          borderBottom: '1px solid var(--color-border, #e0e0e0)',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '0.75rem',
          background: 'var(--color-card, #fff)',
        }}
      >
        {/* Search */}
        <div style={{ position: 'relative', width: 300 }}>
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
            className="form-input"
            style={{ width: '100%', paddingRight: '2rem' }}
            aria-label="Search for a narrator"
          />
          {searchInput && (
            <button
              onClick={() => {
                setSearchInput('')
                setSearchOpen(false)
              }}
              style={{
                position: 'absolute',
                right: 8,
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: '1rem',
                color: '#666',
              }}
              aria-label="Clear search"
            >
              x
            </button>
          )}

          {searchOpen && searchInput && searchResults && searchResults.items.length > 0 && (
            <div
              className="search-dropdown"
              style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                right: 0,
                zIndex: 'var(--z-dropdown, 100)',
                background: 'var(--color-card, #fff)',
                border: '1px solid var(--color-border, #ddd)',
                borderRadius: 'var(--radius-md, 6px)',
                maxHeight: 240,
                overflowY: 'auto',
                boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
              }}
            >
              {searchResults.items.map((n) => (
                <div
                  key={n.id}
                  onClick={() => handleSelectSearch(n.id)}
                  className="search-dropdown-item"
                  style={{
                    padding: '0.5rem 0.75rem',
                    cursor: 'pointer',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <span>{n.name_en}</span>
                  <span dir="rtl" lang="ar" style={{ color: '#666', fontSize: '0.875rem' }}>
                    {n.name_ar}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Depth control */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <span style={{ fontSize: '0.875rem', color: 'var(--color-muted-foreground, #555)' }}>Depth:</span>
          {[1, 2, 3].map((d) => (
            <button
              key={d}
              onClick={() => setDepth(d)}
              title="Number of transmission steps from selected narrator"
              style={{
                padding: '0.25rem 0.625rem',
                border: '1px solid var(--color-border, #ccc)',
                borderRadius: 'var(--radius-sm, 4px)',
                background:
                  d === depth ? 'var(--color-primary, oklch(0.55 0.14 45))' : 'transparent',
                color: d === depth ? '#fff' : 'inherit',
                cursor: 'pointer',
                fontWeight: d === depth ? 600 : 400,
                fontSize: '0.875rem',
              }}
            >
              {d}
            </button>
          ))}
        </div>

        {/* Layout toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <span style={{ fontSize: '0.875rem', color: 'var(--color-muted-foreground, #555)' }}>Layout:</span>
          {(['force', 'hierarchy', 'radial'] as LayoutMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => setLayoutMode(mode)}
              style={{
                padding: '0.25rem 0.5rem',
                border: '1px solid var(--color-border, #ccc)',
                borderRadius: 'var(--radius-sm, 4px)',
                background:
                  mode === layoutMode
                    ? 'var(--color-primary, oklch(0.55 0.14 45))'
                    : 'transparent',
                color: mode === layoutMode ? '#fff' : 'inherit',
                cursor: 'pointer',
                fontSize: '0.8rem',
                textTransform: 'capitalize',
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
            style={{ fontSize: '0.875rem', color: 'var(--color-primary, #1a73e8)' }}
          >
            Clear highlight
          </button>
        )}

        {isLoading && <span style={{ fontSize: '0.875rem', color: '#888' }}>Loading...</span>}
      </div>

      {/* --- Node limit warning --- */}
      {overLimit && (
        <div
          style={{
            padding: '0.5rem 1rem',
            background: 'var(--color-warning, #ffa726)',
            color: '#333',
            fontSize: '0.875rem',
          }}
        >
          This query returned {allNodes.length} nodes. For performance, results are capped at{' '}
          {NODE_LIMIT}. Apply filters or reduce depth.
          <button
            onClick={() => setFilterOpen(true)}
            className="btn"
            style={{ marginLeft: '0.5rem', fontSize: '0.8rem' }}
          >
            Open Filters
          </button>
        </div>
      )}

      {/* --- MAIN CONTENT --- */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', position: 'relative' }}>
        {/* --- GRAPH CANVAS --- */}
        <div
          ref={containerRef}
          style={{
            flex: 1,
            position: 'relative',
            background: 'var(--graph-bg, #fafafa)',
          }}
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
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                color: '#888',
                gap: '1rem',
              }}
            >
              <svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="#bbb">
                <circle cx="16" cy="16" r="4" />
                <circle cx="48" cy="16" r="4" />
                <circle cx="32" cy="48" r="4" />
                <circle cx="48" cy="48" r="4" />
                <line x1="20" y1="16" x2="44" y2="16" />
                <line x1="18" y1="20" x2="30" y2="44" />
                <line x1="34" y1="48" x2="44" y2="48" />
              </svg>
              <p>Search for a narrator to begin exploring the transmission network.</p>
              <p style={{ fontSize: '0.875rem' }}>
                Try:{' '}
                {SUGGESTED_NARRATORS.map((name, i) => (
                  <span key={name}>
                    {i > 0 && ', '}
                    <button
                      onClick={() => handleSuggestedSearch(name)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#1a73e8',
                        cursor: 'pointer',
                        textDecoration: 'underline',
                        padding: 0,
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
              style={{
                position: 'absolute',
                top: 12,
                left: 12,
                background: 'var(--color-card, #fff)',
                border: '1px solid var(--color-border, #ddd)',
                borderRadius: 'var(--radius-md, 6px)',
                padding: '0.5rem 0.75rem',
                fontSize: '0.8rem',
                pointerEvents: 'none',
                zIndex: 10,
                maxWidth: 280,
                boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
              }}
            >
              <div style={{ fontWeight: 600 }}>
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
              style={{
                position: 'absolute',
                top: 12,
                right: detailOpen ? 340 : 12,
                background: 'var(--color-card, #fff)',
                border: '1px solid var(--color-border, #ddd)',
                borderRadius: 'var(--radius-md, 6px)',
                padding: '0.75rem',
                fontSize: '0.8rem',
                zIndex: 10,
                width: 220,
                boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Legend</div>

              <div style={{ marginBottom: '0.5rem' }}>
                <div style={{ fontWeight: 500, marginBottom: '0.25rem' }}>Node size: degree</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <svg width="8" height="8">
                    <circle cx="4" cy="4" r="3" fill="#999" />
                  </svg>
                  1-5
                  <svg width="16" height="16">
                    <circle cx="8" cy="8" r="6" fill="#999" />
                  </svg>
                  6-20
                  <svg width="24" height="24">
                    <circle cx="12" cy="12" r="9" fill="#999" />
                  </svg>
                  21+
                </div>
              </div>

              <div style={{ marginBottom: '0.5rem' }}>
                <div style={{ fontWeight: 500, marginBottom: '0.25rem' }}>
                  Node color: community
                </div>
                {communities.map(([cid, count]) => (
                  <div key={cid} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    <span
                      style={{
                        display: 'inline-block',
                        width: 10,
                        height: 10,
                        borderRadius: '50%',
                        background: communityColor(cid),
                      }}
                    />
                    Community {cid} ({count})
                  </div>
                ))}
              </div>

              <div style={{ marginBottom: '0.5rem' }}>
                <div style={{ fontWeight: 500, marginBottom: '0.25rem' }}>
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
            <div
              style={{
                position: 'absolute',
                bottom: 40,
                left: 12,
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
                zIndex: 10,
              }}
            >
              {[
                { label: '+', title: 'Zoom in' },
                { label: '-', title: 'Zoom out' },
              ].map((btn) => (
                <button
                  key={btn.label}
                  title={btn.title}
                  aria-label={btn.title}
                  style={{
                    width: 32,
                    height: 32,
                    border: '1px solid var(--color-border, #ccc)',
                    borderRadius: 'var(--radius-sm, 4px)',
                    background: 'var(--color-card, #fff)',
                    cursor: 'pointer',
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
            style={{
              width: 320,
              borderLeft: '1px solid var(--color-border, #e0e0e0)',
              background: 'var(--color-card, #fff)',
              overflowY: 'auto',
              padding: '1rem',
              flexShrink: 0,
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '1rem',
              }}
            >
              <span
                style={{
                  fontSize: '0.75rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  color: '#888',
                }}
              >
                Narrator
              </span>
              <button
                onClick={() => setDetailOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '1rem',
                  color: '#666',
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
              <p style={{ color: '#888', fontSize: '0.875rem' }}>Loading details...</p>
            )}
          </div>
        )}
      </div>

      {/* --- STATUS BAR --- */}
      <div
        style={{
          padding: '0.25rem 1rem',
          borderTop: '1px solid var(--color-border, #e0e0e0)',
          fontSize: '0.75rem',
          color: '#888',
          display: 'flex',
          gap: '1.5rem',
          background: 'var(--color-card, #fff)',
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
          style={{
            fontSize: '1.25rem',
            fontFamily: "var(--font-arabic, 'Noto Naskh Arabic', serif)",
            marginBottom: '0.25rem',
          }}
        >
          {narrator.name_ar}
        </div>
      )}
      <div style={{ fontSize: '1rem', fontWeight: 500, marginBottom: '1rem' }}>
        {narrator.name_en}
      </div>

      {/* Metadata */}
      <div style={{ fontSize: '0.85rem', lineHeight: 1.6, marginBottom: '1rem' }}>
        {narrator.kunya && (
          <div>
            <span style={{ color: '#888' }}>Kunya:</span> {narrator.kunya}
          </div>
        )}
        {narrator.nisba && (
          <div>
            <span style={{ color: '#888' }}>Nisba:</span> {narrator.nisba}
          </div>
        )}
        {narrator.generation && (
          <div>
            <span style={{ color: '#888' }}>Generation:</span> {narrator.generation}
          </div>
        )}
        <div>
          <span style={{ color: '#888' }}>Birth:</span>{' '}
          {narrator.birth_year_ah != null ? `${narrator.birth_year_ah} AH` : '\u2014'}
          {' | '}
          <span style={{ color: '#888' }}>Death:</span>{' '}
          {narrator.death_year_ah != null ? `${narrator.death_year_ah} AH` : '\u2014'}
        </div>
        {narrator.sect_affiliation && (
          <div>
            <span style={{ color: '#888' }}>Sect:</span> {narrator.sect_affiliation}
          </div>
        )}
        {narrator.trustworthiness_consensus && (
          <div>
            <span style={{ color: '#888' }}>Trustworthiness:</span>{' '}
            {narrator.trustworthiness_consensus}
          </div>
        )}
      </div>

      {/* Network statistics */}
      <div
        style={{
          borderTop: '1px solid var(--color-border, #e0e0e0)',
          paddingTop: '0.75rem',
          marginBottom: '1rem',
        }}
      >
        <div
          style={{
            fontSize: '0.75rem',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            color: '#888',
            marginBottom: '0.5rem',
          }}
        >
          Network Statistics
        </div>
        <div style={{ fontSize: '0.85rem', lineHeight: 1.6 }}>
          <div>
            <span style={{ color: '#888' }}>Teachers (in):</span> {narrator.in_degree ?? '\u2014'}
          </div>
          <div>
            <span style={{ color: '#888' }}>Students (out):</span>{' '}
            {narrator.out_degree ?? '\u2014'}
          </div>
          {narrator.betweenness_centrality != null && (
            <div>
              <span style={{ color: '#888' }}>Betweenness:</span>{' '}
              {narrator.betweenness_centrality.toFixed(4)}
            </div>
          )}
          {narrator.pagerank != null && (
            <div>
              <span style={{ color: '#888' }}>PageRank:</span> {narrator.pagerank.toFixed(4)}
            </div>
          )}
          {narrator.community_id != null && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <span style={{ color: '#888' }}>Community:</span> {narrator.community_id}
              <span
                style={{
                  display: 'inline-block',
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  background: communityColor(narrator.community_id),
                }}
              />
            </div>
          )}
        </div>
      </div>

      {/* Chains */}
      <div
        style={{
          borderTop: '1px solid var(--color-border, #e0e0e0)',
          paddingTop: '0.75rem',
          marginBottom: '1rem',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '0.5rem',
          }}
        >
          <span
            style={{
              fontSize: '0.75rem',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: '#888',
            }}
          >
            Chains ({chainsTotal} total)
          </span>
        </div>
        <div style={{ maxHeight: 200, overflowY: 'auto' }}>
          {chains.length === 0 && (
            <div style={{ color: '#999', fontSize: '0.85rem' }}>No chains found.</div>
          )}
          {chains.map((c) => (
            <div
              key={c.chain_id}
              onClick={() => onChainSelect(c)}
              style={{
                padding: '0.375rem 0',
                borderBottom: '1px solid #f0f0f0',
                cursor: 'pointer',
                fontSize: '0.8rem',
              }}
            >
              <div style={{ fontWeight: 500 }}>
                {c.grade && <span style={{ color: '#888' }}>[{c.grade}]</span>}{' '}
                {c.matn_en || c.hadith_id}
              </div>
              {c.matn_ar && (
                <div
                  dir="rtl"
                  lang="ar"
                  style={{
                    color: '#666',
                    fontSize: '0.75rem',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    maxWidth: '100%',
                  }}
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
        style={{
          display: 'block',
          textAlign: 'center',
          color: '#1a73e8',
          fontSize: '0.85rem',
          textDecoration: 'none',
          padding: '0.5rem',
          border: '1px solid var(--color-border, #ddd)',
          borderRadius: 'var(--radius-md, 6px)',
        }}
      >
        View Full Profile
      </Link>
    </div>
  )
}
