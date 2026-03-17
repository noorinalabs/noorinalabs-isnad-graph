import { useState, useCallback, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchGraphNetwork, fetchNarrators } from '../api/client'
import ForceGraph from '../components/ForceGraph'
import type { GraphNode, GraphEdge } from '../types/api'

export default function GraphExplorerPage() {
  const [searchInput, setSearchInput] = useState('')
  const [selectedNarratorId, setSelectedNarratorId] = useState<string | null>(null)
  const [depth, setDepth] = useState(1)
  const [allNodes, setAllNodes] = useState<GraphNode[]>([])
  const [allEdges, setAllEdges] = useState<GraphEdge[]>([])
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })

  const { data: searchResults } = useQuery({
    queryKey: ['narrator-search', searchInput],
    queryFn: () => fetchNarrators(1, 10, searchInput),
    enabled: searchInput.length > 0,
  })

  const { data: networkData, isLoading } = useQuery({
    queryKey: ['graph-network', selectedNarratorId, depth],
    queryFn: () => fetchGraphNetwork(selectedNarratorId!, depth),
    enabled: selectedNarratorId != null,
  })

  useEffect(() => {
    if (!networkData) return
    setAllNodes((prev) => {
      const existing = new Set(prev.map((n) => n.id))
      const newNodes = networkData.nodes.filter((n) => !existing.has(n.id))
      return [...prev, ...newNodes]
    })
    setAllEdges((prev) => {
      const existing = new Set(prev.map((e) => `${e.source}-${e.target}`))
      const newEdges = networkData.edges.filter((e) => !existing.has(`${e.source}-${e.target}`))
      return [...prev, ...newEdges]
    })
  }, [networkData])

  useEffect(() => {
    if (!containerRef.current) return
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) {
        setDimensions({
          width: entry.contentRect.width,
          height: Math.max(500, entry.contentRect.height),
        })
      }
    })
    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  const handleNodeClick = useCallback((nodeId: string) => {
    setSelectedNarratorId(nodeId)
  }, [])

  const handleReset = useCallback(() => {
    setAllNodes([])
    setAllEdges([])
    setSelectedNarratorId(null)
    setSearchInput('')
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)' }}>
      <div style={{ marginBottom: '1rem' }}>
        <h2 style={{ margin: '0 0 0.5rem' }}>Graph Explorer</h2>
        <p className="muted-text" style={{ margin: '0 0 1rem' }}>
          Interactive force-directed graph. Search for a narrator to start, then click nodes to
          expand.
        </p>

        <div className="flex-row" style={{ flexWrap: 'wrap' }}>
          <input
            type="text"
            placeholder="Search for a narrator to start..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="form-input"
            style={{ width: 300 }}
          />
          <label className="flex-row" style={{ gap: '0.25rem' }}>
            Depth:
            <select
              value={depth}
              onChange={(e) => setDepth(Number(e.target.value))}
              style={{ padding: '0.25rem' }}
            >
              <option value={1}>1</option>
              <option value={2}>2</option>
              <option value={3}>3</option>
            </select>
          </label>
          <button onClick={handleReset} className="btn">
            Reset
          </button>
          {isLoading && <span className="muted-text">Loading...</span>}
        </div>

        {searchInput && searchResults && (
          <div className="search-dropdown">
            {searchResults.items.map((n) => (
              <div
                key={n.id}
                onClick={() => {
                  setSelectedNarratorId(n.id)
                  setSearchInput('')
                }}
                className="search-dropdown-item"
              >
                <span style={{ direction: 'rtl' }}>{n.name_ar}</span>
                {n.name_en && (
                  <span style={{ marginLeft: '0.5rem', color: '#666' }}>
                    ({n.name_en})
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div ref={containerRef} className="graph-container">
        {allNodes.length > 0 ? (
          <ForceGraph
            nodes={allNodes}
            edges={allEdges}
            onNodeClick={handleNodeClick}
            width={dimensions.width}
            height={dimensions.height}
          />
        ) : (
          <div className="graph-placeholder">
            Search for a narrator above to begin exploring the graph.
          </div>
        )}
      </div>

      {allNodes.length > 0 && (
        <div style={{ marginTop: '0.5rem' }} className="small-muted">
          {allNodes.length} nodes, {allEdges.length} edges loaded
        </div>
      )}
    </div>
  )
}
