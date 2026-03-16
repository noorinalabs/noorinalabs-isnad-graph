import { useState, useRef, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import * as d3 from 'd3'
import { fetchTimeline } from '../api/client'
import type { TimelineEntry } from '../types/api'

const MARGIN = { top: 30, right: 30, bottom: 40, left: 60 }

export default function TimelinePage() {
  const svgRef = useRef<SVGSVGElement | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<TimelineEntry | null>(null)
  const [yearRange, setYearRange] = useState<[number, number]>([0, 300])

  const {
    data: timelineData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['timeline', yearRange[0], yearRange[1]],
    queryFn: () => fetchTimeline(yearRange[0], yearRange[1]),
  })

  const events = timelineData?.entries

  const handleEventClick = useCallback((event: TimelineEntry) => {
    setSelectedEvent((prev) => (prev?.id === event.id ? null : event))
  }, [])

  useEffect(() => {
    if (!events?.length || !svgRef.current) return

    const svg = d3.select(svgRef.current)
    const width = svgRef.current.clientWidth || 800
    const height = Math.max(400, events.length * 30 + MARGIN.top + MARGIN.bottom)

    svg.attr('height', height)
    svg.selectAll('*').remove()

    const allYears = events.flatMap((e) => [e.year_ah, e.end_year_ah ?? e.year_ah])
    const xMin = d3.min(allYears) ?? 0
    const xMax = d3.max(allYears) ?? 300

    const xScale = d3
      .scaleLinear()
      .domain([xMin - 10, xMax + 10])
      .range([MARGIN.left, width - MARGIN.right])

    const yScale = d3
      .scaleBand<number>()
      .domain(events.map((_e, i) => i))
      .range([MARGIN.top, height - MARGIN.bottom])
      .padding(0.3)

    svg
      .append('g')
      .attr('transform', `translate(0,${height - MARGIN.bottom})`)
      .call(d3.axisBottom(xScale).tickFormat((d) => `${d} AH`))
      .selectAll('text')
      .style('font-size', '11px')

    const bars = svg
      .selectAll('.event-bar')
      .data(events)
      .join('g')
      .attr('class', 'event-bar')
      .style('cursor', 'pointer')

    bars
      .append('rect')
      .attr('x', (d) => xScale(d.year_ah))
      .attr('y', (_d, i) => yScale(i) ?? 0)
      .attr('width', (d) =>
        Math.max(4, xScale(d.end_year_ah ?? d.year_ah) - xScale(d.year_ah)),
      )
      .attr('height', yScale.bandwidth())
      .attr('rx', 3)
      .attr('fill', '#1a73e8')
      .attr('opacity', 0.75)

    bars
      .append('text')
      .attr('x', (d) => xScale(d.year_ah) - 4)
      .attr('y', (_d, i) => (yScale(i) ?? 0) + yScale.bandwidth() / 2)
      .attr('text-anchor', 'end')
      .attr('dominant-baseline', 'central')
      .style('font-size', '11px')
      .style('fill', '#333')
      .text((d) => d.name)

    bars.on('click', (_event, d) => handleEventClick(d))
  }, [events, handleEventClick])

  return (
    <div>
      <h2>Timeline</h2>
      <p style={{ color: '#666', marginBottom: '1rem' }}>
        Historical events and narrator activity periods (Anno Hegirae).
      </p>

      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', alignItems: 'center' }}>
        <label>
          From (AH):{' '}
          <input
            type="number"
            value={yearRange[0]}
            onChange={(e) => setYearRange([Number(e.target.value), yearRange[1]])}
            style={{ width: 80, padding: '0.25rem' }}
          />
        </label>
        <label>
          To (AH):{' '}
          <input
            type="number"
            value={yearRange[1]}
            onChange={(e) => setYearRange([yearRange[0], Number(e.target.value)])}
            style={{ width: 80, padding: '0.25rem' }}
          />
        </label>
      </div>

      {isLoading && <p>Loading timeline...</p>}
      {error && <p style={{ color: 'red' }}>Error: {(error as Error).message}</p>}

      <div style={{ display: 'flex', gap: '1.5rem' }}>
        <div style={{ flex: 1, overflowX: 'auto' }}>
          <svg ref={svgRef} width="100%" height={400} />
        </div>

        {selectedEvent && (
          <div
            style={{
              width: 300,
              padding: '1rem',
              border: '1px solid #ddd',
              borderRadius: 6,
              background: '#fafafa',
            }}
          >
            <h3 style={{ margin: '0 0 0.5rem' }}>{selectedEvent.name}</h3>
            <p style={{ color: '#666', fontSize: '0.875rem' }}>
              {selectedEvent.year_ah}
              {selectedEvent.end_year_ah ? ` - ${selectedEvent.end_year_ah}` : ''} AH
            </p>
            {selectedEvent.description && <p>{selectedEvent.description}</p>}
            {selectedEvent.narrator_count > 0 && (
              <p style={{ color: '#666', fontSize: '0.875rem' }}>
                {selectedEvent.narrator_count} active narrators
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
