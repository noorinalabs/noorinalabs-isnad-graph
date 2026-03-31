import { useState, useRef, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import * as d3 from 'd3'
import { fetchTimeline, fetchTimelineRange } from '../api/client'
import type { TimelineEntry } from '../types/api'

const MARGIN = { top: 30, right: 30, bottom: 40, left: 60 }
const DEFAULT_RANGE: [number, number] = [0, 300]

export default function TimelinePage() {
  const svgRef = useRef<SVGSVGElement | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<TimelineEntry | null>(null)
  const [yearRange, setYearRange] = useState<[number, number] | null>(null)

  const { data: rangeData } = useQuery({
    queryKey: ['timeline-range'],
    queryFn: fetchTimelineRange,
    staleTime: 5 * 60 * 1000,
  })

  // Set year range from data once loaded
  useEffect(() => {
    if (rangeData && yearRange === null) {
      setYearRange([rangeData.min_year_ah, rangeData.max_year_ah])
    }
  }, [rangeData, yearRange])

  const effectiveRange = yearRange ?? (rangeData ? [rangeData.min_year_ah, rangeData.max_year_ah] : DEFAULT_RANGE) as [number, number]

  const {
    data: timelineData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['timeline', effectiveRange[0], effectiveRange[1]],
    queryFn: () => fetchTimeline(effectiveRange[0], effectiveRange[1]),
  })

  const events = timelineData?.entries

  const handleEventClick = useCallback((event: TimelineEntry) => {
    setSelectedEvent((prev) => (prev?.id === event.id ? null : event))
  }, [])

  useEffect(() => {
    if (!svgRef.current) return

    const svg = d3.select(svgRef.current)
    const width = svgRef.current.clientWidth || 800

    if (!events?.length) {
      svg.attr('height', 400)
      svg.selectAll('.x-axis').remove()
      svg.selectAll('.event-bar').remove()
      return
    }

    const height = Math.max(400, events.length * 30 + MARGIN.top + MARGIN.bottom)
    svg.attr('height', height)

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

    // --- X Axis: enter/update ---
    let axisG = svg.selectAll<SVGGElement, null>('.x-axis').data([null])
    axisG = axisG
      .enter()
      .append('g')
      .attr('class', 'x-axis')
      .merge(axisG)

    axisG
      .attr('transform', `translate(0,${height - MARGIN.bottom})`)
      .call(d3.axisBottom(xScale).tickFormat((d) => `${d} AH`))
      .selectAll('text')
      .style('font-size', '11px')

    // --- Event bars: enter/update/exit ---
    const barGroups = svg
      .selectAll<SVGGElement, TimelineEntry>('.event-bar')
      .data(events, (d) => d.id)

    // Exit: remove bars no longer in data
    barGroups.exit().remove()

    // Enter: create new bar groups
    const barEnter = barGroups
      .enter()
      .append('g')
      .attr('class', 'event-bar')
      .style('cursor', 'pointer')

    barEnter.append('rect').attr('rx', 3).attr('fill', 'var(--color-primary)').attr('opacity', 0.75)
    barEnter.append('text')
      .attr('text-anchor', 'end')
      .attr('dominant-baseline', 'central')
      .style('font-size', '11px')
      .style('fill', 'var(--color-foreground)')

    // Merge: update all (enter + existing)
    const barMerged = barEnter.merge(barGroups)

    barMerged
      .select('rect')
      .attr('x', (d) => xScale(d.year_ah))
      .attr('y', (_d, i) => yScale(i) ?? 0)
      .attr('width', (d) =>
        Math.max(4, xScale(d.end_year_ah ?? d.year_ah) - xScale(d.year_ah)),
      )
      .attr('height', yScale.bandwidth())

    barMerged
      .select('text')
      .attr('x', (d) => xScale(d.year_ah) - 4)
      .attr('y', (_d, i) => (yScale(i) ?? 0) + yScale.bandwidth() / 2)
      .text((d) => d.name)

    barMerged.on('click', (_event, d) => handleEventClick(d))
  }, [events, handleEventClick])

  return (
    <div>
      <h2 className="page-heading">Timeline</h2>
      <p className="muted-text" style={{ marginBottom: 'var(--spacing-4)' }}>
        Historical events and narrator activity periods (Anno Hegirae).
      </p>

      <div className="timeline-controls">
        <label>
          From (AH):{' '}
          <input
            type="number"
            value={effectiveRange[0]}
            onChange={(e) => setYearRange([Number(e.target.value), effectiveRange[1]])}
            className="form-input-sm"
          />
        </label>
        <label>
          To (AH):{' '}
          <input
            type="number"
            value={effectiveRange[1]}
            onChange={(e) => setYearRange([effectiveRange[0], Number(e.target.value)])}
            className="form-input-sm"
          />
        </label>
      </div>

      {isLoading && (
        <div>
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton skeleton-row" style={{ width: `${80 - i * 10}%` }} />
          ))}
        </div>
      )}
      {error && <p className="error-text">Error: {(error as Error).message}</p>}

      <div className="timeline-body">
        <div className="timeline-chart">
          <svg ref={svgRef} width="100%" height={400} role="img" aria-label={`Timeline chart showing events from ${effectiveRange[0]} to ${effectiveRange[1]} AH`} />
        </div>

        {selectedEvent && (
          <div className="timeline-detail">
            <h3>{selectedEvent.name}</h3>
            <p className="small-muted">
              {selectedEvent.year_ah}
              {selectedEvent.end_year_ah ? ` - ${selectedEvent.end_year_ah}` : ''} AH
            </p>
            {selectedEvent.description && <p>{selectedEvent.description}</p>}
            {selectedEvent.narrator_count > 0 && (
              <p className="small-muted">
                {selectedEvent.narrator_count} active narrators
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
