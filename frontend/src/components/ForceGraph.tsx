import { useRef, useEffect, useCallback } from 'react'
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d'
import type { GraphNode, GraphEdge } from '../types/api'

const COMMUNITY_COLORS = [
  '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
  '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
  '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
]

function communityColor(id: number | null): string {
  if (id == null) return '#999'
  return COMMUNITY_COLORS[id % COMMUNITY_COLORS.length] ?? '#999'
}

interface ForceGraphProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  onNodeClick?: (nodeId: string) => void
  width?: number
  height?: number
}

interface InternalNode {
  id: string
  label: string
  community_id: number | null
  type: string
  x?: number
  y?: number
}

export default function ForceGraph({ nodes, edges, onNodeClick, width, height }: ForceGraphProps) {
  const fgRef = useRef<ForceGraphMethods | undefined>(undefined)

  const graphData = {
    nodes: nodes.map((n): InternalNode => ({ ...n })),
    links: edges.map((e) => ({
      source: e.source,
      target: e.target,
      relationship: e.relationship,
    })),
  }

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

  const nodeCanvasObject = useCallback(
    (node: InternalNode, ctx: CanvasRenderingContext2D) => {
      const x = node.x ?? 0
      const y = node.y ?? 0
      const radius = 6
      const color = communityColor(node.community_id)

      ctx.beginPath()
      ctx.arc(x, y, radius, 0, 2 * Math.PI)
      ctx.fillStyle = color
      ctx.fill()
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 1.5
      ctx.stroke()

      const label = node.label ?? String(node.id)
      if (label) {
        ctx.font = '4px sans-serif'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        ctx.fillStyle = '#333'
        ctx.fillText(label, x, y + radius + 2)
      }
    },
    [],
  )

  return (
    <ForceGraph2D
      ref={fgRef}
      graphData={graphData}
      width={width}
      height={height ?? 600}
      nodeCanvasObject={nodeCanvasObject}
      onNodeClick={handleNodeClick}
      linkDirectionalArrowLength={4}
      linkDirectionalArrowRelPos={1}
      linkColor={() => '#ccc'}
      cooldownTicks={100}
    />
  )
}
