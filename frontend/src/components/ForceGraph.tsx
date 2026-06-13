import { useRef, useEffect, useCallback, useMemo, useState } from 'react'
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d'
import { dataViz, dataVizDark } from '@noorinalabs/design-system'
import type { GraphNode, GraphEdge } from '../types/api'

/** Read current theme colors from CSS custom properties. */
function getThemeColors() {
  const style = getComputedStyle(document.documentElement)
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
    document.documentElement.classList.contains('dark')
  // Graph/community palette + accent come from the DS data-viz tokens. Canvas can't
  // consume `var()`, so we pick the resolved light/dark constant array by current
  // theme (mirrors how the link colors below switch on `isDark`). The mutation
  // observer in `useThemeColors` re-reads this on theme change for reactivity.
  const viz = isDark ? dataVizDark : dataViz
  return {
    background: style.getPropertyValue('--color-background').trim() || '#fafafa',
    foreground: style.getPropertyValue('--color-foreground').trim() || '#333',
    card: style.getPropertyValue('--color-card').trim() || '#fff',
    muted: style.getPropertyValue('--color-muted-foreground').trim() || '#999',
    community: viz.categorical,
    accent: viz.accent,
    // Pre-computed link colors for canvas (canvas doesn't reliably support color-mix)
    linkDefault: isDark ? 'rgba(160, 160, 160, 0.4)' : 'rgba(204, 204, 204, 0.4)',
    linkActive: isDark ? 'rgba(160, 160, 160, 0.8)' : 'rgba(204, 204, 204, 0.8)',
    linkDimmed: isDark ? 'rgba(160, 160, 160, 0.1)' : 'rgba(204, 204, 204, 0.1)',
  }
}

/** Hook that returns theme colors and re-reads on data-theme changes. */
function useThemeColors() {
  const [colors, setColors] = useState(getThemeColors)

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setColors(getThemeColors())
    })
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme', 'class'],
    })
    return () => observer.disconnect()
  }, [])

  return colors
}

/**
 * Map a community id to a categorical color from the DS data-viz palette.
 *
 * `palette` defaults to the light-mode DS categorical scale so DOM consumers
 * (e.g. the GraphExplorer legend swatches) can call this with just an id, while
 * the canvas renderer passes the theme-reactive `themeColors.community` array so
 * node fills track light/dark mode. The DS palette is CVD-distinguishable and
 * meets WCAG non-text contrast against the matching-mode background. The scale
 * has 10 entries (was 8); >10 communities cycle by modulo.
 */
function communityColor(
  id: number | null | undefined,
  palette: readonly string[] = dataViz.categorical,
): string {
  if (id == null) return '#999'
  return palette[id % palette.length] ?? '#999'
}

/** Map degree to node radius per wireframe spec. */
function nodeRadius(node: GraphNode): number {
  const degree = (node.in_degree ?? 0) + (node.out_degree ?? 0)
  if (degree >= 51) return 16
  if (degree >= 21) return 12
  if (degree >= 6) return 8
  return 4
}

/** Map edge weight to stroke width per wireframe spec. */
function edgeWidth(weight: number): number {
  if (weight >= 21) return 4
  if (weight >= 6) return 3
  if (weight >= 2) return 2
  return 1
}

export interface ForceGraphProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  selectedNodeId: string | null
  highlightedChainNodeIds: Set<string> | null
  onNodeClick?: (nodeId: string) => void
  onNodeHover?: (node: GraphNode | null) => void
  width?: number
  height?: number
}

interface InternalNode {
  id: string
  label: string
  name_ar: string
  name_en: string | null
  community_id?: number | null
  in_degree?: number | null
  out_degree?: number | null
  generation?: string | null
  type: string
  x?: number
  y?: number
  [key: string]: unknown
}

interface InternalLink {
  source: string | InternalNode
  target: string | InternalNode
  relationship: string
  weight: number
}

const REDUCED_MOTION =
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

export default function ForceGraph({
  nodes,
  edges,
  selectedNodeId,
  highlightedChainNodeIds,
  onNodeClick,
  onNodeHover,
  width,
  height,
}: ForceGraphProps) {
  const fgRef = useRef<ForceGraphMethods | undefined>(undefined)
  const themeColors = useThemeColors()

  const graphData = useMemo(
    () => ({
      nodes: nodes.map(
        (n): InternalNode => ({
          id: n.id,
          label: n.label,
          name_ar: n.name_ar,
          name_en: n.name_en,
          community_id: n.community_id,
          in_degree: n.in_degree,
          out_degree: n.out_degree,
          generation: n.generation,
          type: n.type,
        }),
      ),
      links: edges.map(
        (e): InternalLink => ({
          source: e.source,
          target: e.target,
          relationship: e.relationship,
          weight: e.weight,
        }),
      ),
    }),
    [nodes, edges],
  )

  // Build adjacency set for selection highlighting
  const adjacentNodes = useMemo(() => {
    if (!selectedNodeId) return null
    const adj = new Set<string>()
    adj.add(selectedNodeId)
    for (const e of edges) {
      if (e.source === selectedNodeId) adj.add(e.target)
      if (e.target === selectedNodeId) adj.add(e.source)
    }
    return adj
  }, [selectedNodeId, edges])

  // Node lookup by id for radius computation
  const nodeMap = useMemo(() => {
    const m = new Map<string, GraphNode>()
    for (const n of nodes) m.set(n.id, n)
    return m
  }, [nodes])

  useEffect(() => {
    if (fgRef.current) {
      fgRef.current.d3Force('charge')?.strength(-120)
    }
    return () => {
      if (fgRef.current) {
        fgRef.current.pauseAnimation()
      }
    }
  }, [])

  const handleNodeClick = useCallback(
    (node: { id?: string | number }) => {
      if (onNodeClick && node.id != null) {
        onNodeClick(String(node.id))
      }
    },
    [onNodeClick],
  )

  const handleNodeHoverCb = useCallback(
    (node: object | null) => {
      if (!onNodeHover) return
      if (!node) {
        onNodeHover(null)
        return
      }
      const n = node as InternalNode
      onNodeHover(nodeMap.get(n.id) ?? null)
    },
    [onNodeHover, nodeMap],
  )

  const nodeCanvasObject = useCallback(
    (obj: object, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const node = obj as InternalNode
      const x = node.x ?? 0
      const y = node.y ?? 0
      const origNode = nodeMap.get(node.id)
      const r = origNode ? nodeRadius(origNode) : 6
      const color = communityColor(node.community_id, themeColors.community)
      const isSelected = selectedNodeId === node.id
      const isChainHighlighted = highlightedChainNodeIds?.has(node.id)

      // Determine opacity based on state
      let opacity = 1.0
      if (highlightedChainNodeIds) {
        opacity = isChainHighlighted ? 1.0 : 0.15
      } else if (selectedNodeId) {
        opacity = adjacentNodes?.has(node.id) ? 1.0 : 0.2
      }

      ctx.globalAlpha = opacity

      // Draw filled circle
      ctx.beginPath()
      ctx.arc(x, y, r, 0, 2 * Math.PI)
      ctx.fillStyle = color
      ctx.fill()
      ctx.strokeStyle = themeColors.card
      ctx.lineWidth = 1.5
      ctx.stroke()

      // Selection / chain highlight ring
      if (isSelected || isChainHighlighted) {
        ctx.beginPath()
        ctx.arc(x, y, r + 2, 0, 2 * Math.PI)
        ctx.strokeStyle = themeColors.accent
        ctx.lineWidth = 3
        ctx.stroke()
      }

      // Level-of-detail labels
      const showAllLabels = globalScale > 3
      const showSelectedLabel = globalScale > 1.5

      if (showAllLabels || ((isSelected || isChainHighlighted) && showSelectedLabel)) {
        const fontSize = Math.min(12, 12 / globalScale)

        // English label below node
        const labelText = node.name_en || node.label
        if (labelText) {
          ctx.font = `${fontSize}px sans-serif`
          ctx.textAlign = 'center'
          ctx.textBaseline = 'top'
          ctx.fillStyle = themeColors.foreground
          ctx.fillText(labelText, x, y + r + 2)
        }

        // Arabic label above node at high zoom
        if (showAllLabels && node.name_ar) {
          ctx.font = `${fontSize}px 'Noto Naskh Arabic', serif`
          ctx.textAlign = 'center'
          ctx.textBaseline = 'bottom'
          ctx.fillStyle = themeColors.foreground
          ctx.fillText(node.name_ar, x, y - r - 2)
        }
      }

      ctx.globalAlpha = 1.0
    },
    [nodeMap, selectedNodeId, highlightedChainNodeIds, adjacentNodes, themeColors],
  )

  const linkColor = useCallback(
    (link: object) => {
      const l = link as InternalLink
      const sourceId = typeof l.source === 'string' ? l.source : l.source?.id
      const targetId = typeof l.target === 'string' ? l.target : l.target?.id

      if (highlightedChainNodeIds) {
        if (
          sourceId &&
          targetId &&
          highlightedChainNodeIds.has(sourceId) &&
          highlightedChainNodeIds.has(targetId)
        ) {
          return themeColors.accent
        }
        return themeColors.linkDimmed
      }

      if (selectedNodeId) {
        if (sourceId === selectedNodeId || targetId === selectedNodeId) {
          return themeColors.linkActive
        }
        return themeColors.linkDimmed
      }

      return themeColors.linkDefault
    },
    [selectedNodeId, highlightedChainNodeIds, themeColors],
  )

  const linkWidthCb = useCallback(
    (link: object) => {
      const l = link as InternalLink
      const sourceId = typeof l.source === 'string' ? l.source : l.source?.id
      const targetId = typeof l.target === 'string' ? l.target : l.target?.id

      if (
        highlightedChainNodeIds &&
        sourceId &&
        targetId &&
        highlightedChainNodeIds.has(sourceId) &&
        highlightedChainNodeIds.has(targetId)
      ) {
        return 3
      }
      return edgeWidth(l.weight)
    },
    [highlightedChainNodeIds],
  )

  const linkDashPattern = useCallback((link: object) => {
    const l = link as InternalLink
    return l.relationship === 'STUDIED_UNDER' ? [4, 2] : []
  }, [])

  return (
    <ForceGraph2D
      ref={fgRef}
      graphData={graphData}
      width={width}
      height={height ?? 600}
      backgroundColor={themeColors.background}
      nodeCanvasObject={nodeCanvasObject}
      nodePointerAreaPaint={(obj: object, color: string, ctx: CanvasRenderingContext2D) => {
        const node = obj as InternalNode
        const origNode = nodeMap.get(node.id)
        const r = origNode ? nodeRadius(origNode) : 6
        ctx.beginPath()
        ctx.arc(node.x ?? 0, node.y ?? 0, r + 2, 0, 2 * Math.PI)
        ctx.fillStyle = color
        ctx.fill()
      }}
      onNodeClick={handleNodeClick}
      onNodeHover={handleNodeHoverCb}
      linkDirectionalArrowLength={6}
      linkDirectionalArrowRelPos={0.95}
      linkColor={linkColor}
      linkWidth={linkWidthCb}
      linkLineDash={linkDashPattern}
      cooldownTicks={REDUCED_MOTION ? 0 : 300}
      warmupTicks={REDUCED_MOTION ? 300 : 0}
      enableNodeDrag={true}
      enableZoomInteraction={true}
      enablePanInteraction={true}
    />
  )
}

export { communityColor, nodeRadius, edgeWidth }
