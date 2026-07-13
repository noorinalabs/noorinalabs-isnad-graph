import { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  fetchGraphNetwork,
  fetchNarrators,
  fetchNarrator,
  fetchNarratorChains,
} from '../api/client'
import ForceGraph from '../components/ForceGraph'
import { communityColor } from '../components/ForceGraph'
import { Badge } from '../components/ui/Badge'
import type { GraphNode, GraphEdge, Narrator, ChainSummary } from '../types/api'
import { computeTabaqaLayers, tabaqaRankByNode } from '../lib/tabaqa'

const NODE_LIMIT = 5000

// Number of narrators to fetch as default-graph seed candidates. We pick the
// highest-degree narrator among them to render a non-empty landing subgraph and
// surface the top few as one-click, ID-seeded suggestion chips (#1031). The
// `/narrators` list endpoint orders by id (≈ uniform over the uuid5 id space),
// so a generous sample reliably contains a well-connected hub to seed from.
const SEED_CANDIDATE_LIMIT = 100
const SUGGESTION_COUNT = 6

type LayoutMode = 'force' | 'hierarchy' | 'radial' | 'tabaqa'

function narratorDegree(n: {
  in_degree: number | null
  out_degree: number | null
}): number {
  return (n.in_degree ?? 0) + (n.out_degree ?? 0)
}

export default function GraphExplorerPage() {
  const { t } = useTranslation()
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
  // Guards the one-shot default-graph auto-seed so it never fights a user's own
  // selection and never re-seeds after an explicit Reset (#1031).
  const didAutoSeedRef = useRef(false)
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

  // Default-graph seed candidates: a sample of real narrators used both to
  // auto-seed a non-empty landing subgraph and to build one-click, ID-seeded
  // suggestion chips (#1031). Degrades gracefully — if `/narrators` is
  // unavailable the page falls back to the empty state with the search box.
  const { data: seedData } = useQuery({
    queryKey: ['graph-seed-narrators'],
    queryFn: () => fetchNarrators(1, SEED_CANDIDATE_LIMIT),
    staleTime: 5 * 60 * 1000,
  })

  // Top narrators by degree — real, existing nodes (no name-search round-trip).
  const suggestedNarrators = useMemo(() => {
    const items = seedData?.items ?? []
    return [...items]
      .sort((a, b) => narratorDegree(b) - narratorDegree(a))
      .slice(0, SUGGESTION_COUNT)
  }, [seedData])

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

  // --- Default-graph auto-seed (#1031) ---
  // On first load, seed the highest-degree narrator's ego network so `/graph` is
  // never blank. Runs once: the ref is set when we seed AND on explicit Reset, so
  // it neither overrides a user selection nor re-seeds a deliberately-cleared canvas.
  useEffect(() => {
    if (didAutoSeedRef.current) return
    if (selectedNarratorId != null) return
    const top = suggestedNarrators[0]
    if (!top) return
    didAutoSeedRef.current = true
    setSelectedNarratorId(top.id)
  }, [suggestedNarrators, selectedNarratorId])

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

  // --- Ṭabaqa (generation) layering (ig#1043) ---
  // Group loaded narrator nodes into chronological generation bands so the
  // isnad-tree can read top→bottom (earliest ṭabaqa first). Narrators with an
  // unknown/unmapped generation fall into a trailing band — see computeTabaqaLayers.
  const tabaqaLayers = useMemo(() => computeTabaqaLayers(allNodes), [allNodes])
  const tabaqaRank = useMemo(() => tabaqaRankByNode(tabaqaLayers), [tabaqaLayers])

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
    // Explicit Reset means "blank canvas" — suppress the default auto-seed so it
    // doesn't immediately repopulate the graph the user just cleared (#1031).
    didAutoSeedRef.current = true
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

  // One-click, ID-seeded suggestion chip: focus the graph on a real narrator
  // directly (no name-search round-trip). Detail panel stays closed for a clean
  // landing view (#1031).
  const handleSelectSuggested = useCallback((narratorId: string) => {
    didAutoSeedRef.current = true
    setSelectedNarratorId(narratorId)
    setSearchInput('')
    setSearchOpen(false)
  }, [])

  const overLimit = allNodes.length > NODE_LIMIT

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 64px)' }}>
      {/* --- TOOLBAR --- */}
      <div className="flex flex-wrap items-center gap-3 border-b border-border bg-card px-4 py-2">
        {/* Search */}
        <div className="relative w-[300px]">
          <input
            ref={searchRef}
            type="text"
            placeholder={t('graph.searchPlaceholder')}
            value={searchInput}
            onChange={(e) => {
              setSearchInput(e.target.value)
              setSearchOpen(true)
            }}
            onFocus={() => setSearchOpen(true)}
            className="form-input w-full pr-8"
            aria-label={t('graph.searchAria')}
          />
          {searchInput && (
            <button
              onClick={() => {
                setSearchInput('')
                setSearchOpen(false)
              }}
              className="absolute right-2 top-1/2 -translate-y-1/2 cursor-pointer border-none text-muted-foreground"
              style={{
                background: 'none',
                fontSize: '1rem',
              }}
              aria-label={t('graph.clearSearch')}
            >
              x
            </button>
          )}

          {searchOpen && searchInput && searchResults && searchResults.items.length > 0 && (
            <div
              className="search-dropdown absolute top-full left-0 right-0 max-h-60 overflow-y-auto rounded-md border border-border bg-card"
              style={{
                zIndex: 'var(--z-dropdown)',
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
          <span className="muted-text" style={{ fontSize: '0.875rem' }}>{t('graph.depth')}</span>
          {[1, 2, 3].map((d) => (
            <button
              key={d}
              onClick={() => setDepth(d)}
              title={t('graph.depthTitle')}
              className="cursor-pointer rounded-sm border border-border px-2.5 py-1"
              style={{
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
          <span className="muted-text" style={{ fontSize: '0.875rem' }}>{t('graph.layout')}</span>
          {(['force', 'hierarchy', 'radial', 'tabaqa'] as LayoutMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => setLayoutMode(mode)}
              className="cursor-pointer rounded-sm border border-border px-2 py-1"
              style={{
                background:
                  mode === layoutMode
                    ? 'var(--color-primary, oklch(0.55 0.14 45))'
                    : 'transparent',
                color: mode === layoutMode ? 'var(--color-primary-foreground)' : 'inherit',
                fontSize: '0.8rem',
              }}
            >
              {t(`graph.layout${mode.charAt(0).toUpperCase()}${mode.slice(1)}`)}
            </button>
          ))}
        </div>

        {/* Filter button */}
        <button
          onClick={() => setFilterOpen(!filterOpen)}
          className="btn"
          style={{ fontSize: '0.875rem' }}
        >
          {t('common.filters')}
        </button>

        {/* Reset */}
        <button onClick={handleReset} className="btn" style={{ fontSize: '0.875rem' }}>
          {t('graph.reset')}
        </button>

        {/* Legend toggle */}
        <button
          onClick={() => setLegendOpen(!legendOpen)}
          className="btn"
          style={{ fontSize: '0.875rem' }}
        >
          {t('graph.legend')}
        </button>

        {/* Chain highlight clear */}
        {highlightedChainNodeIds && (
          <button
            onClick={() => setHighlightedChainNodeIds(null)}
            className="btn text-primary"
            style={{ fontSize: '0.875rem' }}
          >
            {t('graph.clearHighlight')}
          </button>
        )}

        {isLoading && <span className="muted-text" style={{ fontSize: '0.875rem' }}>{t('common.loading')}</span>}
      </div>

      {/* --- Node limit warning --- */}
      {overLimit && (
        <div
          className="bg-warning px-4 py-2 text-warning-foreground"
          style={{
            fontSize: '0.875rem',
          }}
        >
          {t('graph.nodeLimitWarning', { count: allNodes.length, limit: NODE_LIMIT })}
          <button
            onClick={() => setFilterOpen(true)}
            className="btn ml-2"
            style={{ fontSize: '0.8rem' }}
          >
            {t('graph.openFilters')}
          </button>
        </div>
      )}

      {/* --- MAIN CONTENT --- */}
      <div className="relative flex flex-1 overflow-hidden">
        {/* --- GRAPH CANVAS --- */}
        <div
          ref={containerRef}
          className="relative flex-1 bg-background"
          role="application"
          aria-label={t('graph.canvasAria')}
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
              layoutMode={layoutMode}
              nodeLayerRank={layoutMode === 'tabaqa' ? tabaqaRank : null}
              layerCount={tabaqaLayers.length}
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
              <div className="empty-state-heading">{t('graph.emptyHeading')}</div>
              <div className="empty-state-body">
                {t('graph.emptyBody')}
              </div>
              {suggestedNarrators.length > 0 && (
                <p className="mt-4" style={{ fontSize: 'var(--text-sm)' }}>
                  {t('graph.tryPrefix')}{' '}
                  {suggestedNarrators.map((n, i) => (
                    <span key={n.id}>
                      {i > 0 && ', '}
                      <button
                        onClick={() => handleSelectSuggested(n.id)}
                        className="link-primary cursor-pointer border-none p-0 underline"
                        style={{
                          background: 'none',
                          font: 'inherit',
                        }}
                      >
                        {n.name_en || n.name_ar}
                      </button>
                    </span>
                  ))}
                </p>
              )}
            </div>
          )}

          {/* Hover tooltip */}
          {hoveredNode && (
            <div
              className="pointer-events-none absolute top-3 left-3 z-10 max-w-[280px] rounded-md border border-border bg-card px-3 py-2"
              style={{
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
              {hoveredNode.generation && <div>{t('graph.tooltipGen', { generation: hoveredNode.generation })}</div>}
              {hoveredNode.death_year_ah != null && <div>{t('graph.tooltipDeath', { year: hoveredNode.death_year_ah })}</div>}
              <div>
                {t('graph.connections', { count: (hoveredNode.in_degree ?? 0) + (hoveredNode.out_degree ?? 0) })}
              </div>
              {hoveredNode.trustworthiness_consensus && (
                <div>{t('graph.tooltipTrust', { value: hoveredNode.trustworthiness_consensus })}</div>
              )}
            </div>
          )}

          {/* Ṭabaqa generation bands (ig#1043) — annotates the chronological layering */}
          {layoutMode === 'tabaqa' && allNodes.length > 0 && (
            <div
              className="absolute top-1/2 left-3 z-10 max-w-[220px] -translate-y-1/2 rounded-md border border-border bg-card p-3"
              style={{ fontSize: '0.75rem', boxShadow: 'var(--shadow-md)' }}
              data-testid="tabaqa-bands"
            >
              <div className="mb-2 font-semibold">{t('graph.tabaqaBandsTitle')}</div>
              <ol className="m-0 flex list-none flex-col gap-1 p-0">
                {tabaqaLayers.map((layer) => (
                  <li key={layer.key} className="flex items-center justify-between gap-3">
                    <span>{t(layer.labelKey)}</span>
                    <span className="muted-text">{layer.nodeIds.length}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* Legend panel */}
          {legendOpen && (
            <div
              className="absolute top-3 z-10 w-[220px] rounded-md border border-border bg-card p-3"
              style={{
                right: detailOpen ? 340 : 12,
                fontSize: '0.8rem',
                boxShadow: 'var(--shadow-md)',
              }}
            >
              <div className="mb-2 font-semibold">{t('graph.legend')}</div>

              <div className="mb-2">
                <div className="mb-1 font-medium">{t('graph.legendNodeSize')}</div>
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
                  {t('graph.legendNodeColor')}
                </div>
                {communities.map(([cid, count]) => (
                  <div key={cid} className="flex items-center gap-1">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{ background: communityColor(cid) }}
                    />
                    {t('graph.legendCommunity', { id: cid, count })}
                  </div>
                ))}
              </div>

              <div className="mb-2">
                <div className="mb-1 font-medium">
                  {t('graph.legendEdge')}
                </div>
                <div>{t('graph.legendSolid')}</div>
                <div>{t('graph.legendDashed')}</div>
                <div>{t('graph.legendThickness')}</div>
              </div>
            </div>
          )}

          {/* Zoom controls */}
          {allNodes.length > 0 && (
            <div className="absolute bottom-10 left-3 z-10 flex flex-col gap-0.5">
              {[
                { label: '+', title: t('graph.zoomIn') },
                { label: '-', title: t('graph.zoomOut') },
              ].map((btn) => (
                <button
                  key={btn.label}
                  title={btn.title}
                  aria-label={btn.title}
                  className="h-8 w-8 cursor-pointer rounded-sm border border-border bg-card"
                  style={{
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
            className="w-[320px] shrink-0 overflow-y-auto border-l border-border bg-card p-4"
          >
            <div className="mb-4 flex items-center justify-between">
              <span
                className="uppercase text-muted-foreground"
                style={{
                  fontSize: '0.75rem',
                  letterSpacing: '0.05em',
                }}
              >
                {t('graph.narratorLabel')}
              </span>
              <button
                onClick={() => setDetailOpen(false)}
                className="cursor-pointer border-none text-muted-foreground"
                style={{
                  background: 'none',
                  fontSize: '1rem',
                }}
                aria-label={t('graph.closeDetail')}
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
              <p className="muted-text" style={{ fontSize: '0.875rem' }}>{t('graph.loadingDetails')}</p>
            )}
          </div>
        )}
      </div>

      {/* --- STATUS BAR --- */}
      <div
        className="flex gap-6 border-t border-border bg-card px-4 py-1 text-muted-foreground"
        style={{
          fontSize: '0.75rem',
        }}
      >
        <span>
          {t('graph.statusNodesEdges', { nodes: allNodes.length, edges: allEdges.length })}
        </span>
        {communities.length > 0 && (
          <span>
            {t('graph.statusCommunities', { count: communities.length })}
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
  const { t } = useTranslation()
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
            <span className="muted-text">{t('narratorFields.kunya')}:</span> {narrator.kunya}
          </div>
        )}
        {narrator.nisba && (
          <div>
            <span className="muted-text">{t('narratorFields.nisba')}:</span> {narrator.nisba}
          </div>
        )}
        {narrator.generation && (
          <div>
            <span className="muted-text">{t('narratorFields.generation')}:</span> {narrator.generation}
          </div>
        )}
        <div>
          <span className="muted-text">{t('narratorFields.birth')}:</span>{' '}
          {narrator.birth_year_ah != null ? `${narrator.birth_year_ah} AH` : '\u2014'}
          {' | '}
          <span className="muted-text">{t('narratorFields.death')}:</span>{' '}
          {narrator.death_year_ah != null ? `${narrator.death_year_ah} AH` : '\u2014'}
        </div>
        {narrator.sect_affiliation && (
          <div>
            <span className="muted-text">{t('narratorFields.sect')}:</span> {narrator.sect_affiliation}
          </div>
        )}
        {narrator.trustworthiness_consensus && (
          <div>
            <span className="muted-text">{t('narratorFields.trustworthiness')}:</span>{' '}
            {narrator.trustworthiness_consensus}
          </div>
        )}
      </div>

      {/* Network statistics */}
      <div
        className="mb-4 border-t border-border pt-3"
      >
        <div
          className="mb-2 uppercase text-muted-foreground"
          style={{
            fontSize: '0.75rem',
            letterSpacing: '0.05em',
          }}
        >
          {t('narratorFields.networkStatistics')}
        </div>
        {/* Honest-leaderboard disclosure (main#958): flag an over-merged node so
            its inflated betweenness (shown below) is read as a fused artifact,
            not a single person. We disclose \u2014 we do not drop or recompute it. */}
        {narrator.over_merged && (
          <div
            role="note"
            aria-label={t('narratorFields.overMerged')}
            className="mb-2 rounded-md border border-border p-2"
          >
            <Badge variant="destructive" className="text-xs">
              {t('narratorFields.overMerged')}
            </Badge>
            <div className="text-destructive" style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
              {t('narratorFields.overMergedExplainer')}
            </div>
            {narrator.over_merge_note && (
              <div className="muted-text" style={{ fontSize: '0.7rem', marginTop: '0.25rem' }}>
                {narrator.over_merge_note}
              </div>
            )}
          </div>
        )}
        <div style={{ fontSize: '0.85rem', lineHeight: 1.6 }}>
          <div>
            <span className="muted-text">{t('narratorFields.teachersIn')}:</span> {narrator.in_degree ?? '\u2014'}
          </div>
          <div>
            <span className="muted-text">{t('narratorFields.studentsOut')}:</span>{' '}
            {narrator.out_degree ?? '\u2014'}
          </div>
          {narrator.betweenness_centrality != null && (
            <div>
              <span className="muted-text">{t('narratorFields.betweenness')}:</span>{' '}
              {narrator.betweenness_centrality.toFixed(4)}
            </div>
          )}
          {narrator.pagerank != null && (
            <div>
              <span className="muted-text">{t('narratorFields.pagerank')}:</span> {narrator.pagerank.toFixed(4)}
            </div>
          )}
          {narrator.community_id != null && (
            <div className="flex items-center gap-1">
              <span className="muted-text">{t('narratorFields.community')}:</span> {narrator.community_id}
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
        className="mb-4 border-t border-border pt-3"
      >
        <div className="mb-2 flex items-center justify-between">
          <span
            className="uppercase text-muted-foreground"
            style={{
              fontSize: '0.75rem',
              letterSpacing: '0.05em',
            }}
          >
            {t('graph.panelChains', { count: chainsTotal })}
          </span>
        </div>
        <div className="max-h-[200px] overflow-y-auto">
          {chains.length === 0 && (
            <div className="muted-text" style={{ fontSize: '0.85rem' }}>{t('graph.panelNoChains')}</div>
          )}
          {chains.map((c) => (
            <div
              key={c.chain_id}
              onClick={() => onChainSelect(c)}
              className="cursor-pointer border-b border-border px-0 py-1.5"
              style={{
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
        className="block rounded-md border border-border p-2 text-center text-primary no-underline"
        style={{
          fontSize: '0.85rem',
        }}
      >
        {t('graph.panelViewProfile')}
      </Link>
    </div>
  )
}
