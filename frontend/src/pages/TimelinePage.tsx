import { useState, useRef, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import * as d3 from 'd3'
import {
  fetchTimeline,
  fetchTimelineRange,
  fetchCollections,
  fetchNarratorTimeline,
} from '../api/client'
import type { TimelineEntry, Collection, NarratorTimelineEntry } from '../types/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'

const MARGIN = { top: 30, right: 30, bottom: 40, left: 180 }
const DEFAULT_RANGE: [number, number] = [0, 300]

function CollectionTimeline({ collections }: { collections: Collection[] }) {
  const { t } = useTranslation()
  const svgRef = useRef<SVGSVGElement | null>(null)
  const navigate = useNavigate()

  const sorted = collections
    .filter((c) => c.compilation_year_ah != null)
    .sort((a, b) => (a.compilation_year_ah ?? 0) - (b.compilation_year_ah ?? 0))

  useEffect(() => {
    if (!svgRef.current || sorted.length === 0) return

    const svg = d3.select(svgRef.current)
    const width = svgRef.current.clientWidth || 800
    const height = Math.max(300, sorted.length * 36 + MARGIN.top + MARGIN.bottom)
    svg.attr('height', height)

    svg.selectAll('*').remove()

    const years = sorted.map((c) => c.compilation_year_ah!)
    const xMin = d3.min(years) ?? 0
    const xMax = d3.max(years) ?? 300

    const xScale = d3
      .scaleLinear()
      .domain([xMin - 20, xMax + 20])
      .range([MARGIN.left, width - MARGIN.right])

    const yScale = d3
      .scaleBand<number>()
      .domain(sorted.map((_c, i) => i))
      .range([MARGIN.top, height - MARGIN.bottom])
      .padding(0.3)

    svg
      .append('g')
      .attr('transform', `translate(0,${height - MARGIN.bottom})`)
      .call(d3.axisBottom(xScale).tickFormat((d) => `${d} AH`))
      .selectAll('text')
      .style('font-size', '11px')

    const groups = svg
      .selectAll<SVGGElement, Collection>('.collection-bar')
      .data(sorted)
      .enter()
      .append('g')
      .attr('class', 'collection-bar')
      .style('cursor', 'pointer')
      .on('click', (_event, d) => navigate(`/collections/${d.id}`))

    groups
      .append('rect')
      .attr('x', MARGIN.left)
      .attr('y', (_d, i) => yScale(i) ?? 0)
      .attr('width', (d) => Math.max(4, xScale(d.compilation_year_ah!) - MARGIN.left))
      .attr('height', yScale.bandwidth())
      .attr('rx', 3)
      .attr('fill', (d) =>
        d.sect.toLowerCase() === 'sunni' ? 'var(--color-sunni)' : 'var(--color-shia)',
      )
      .attr('opacity', 0.7)

    groups
      .append('text')
      .attr('x', MARGIN.left - 8)
      .attr('y', (_d, i) => (yScale(i) ?? 0) + yScale.bandwidth() / 2)
      .attr('text-anchor', 'end')
      .attr('dominant-baseline', 'central')
      .style('font-size', '12px')
      .style('fill', 'var(--color-foreground)')
      .text((d) => d.name_en || d.name_ar)

    groups
      .append('text')
      .attr('x', (d) => xScale(d.compilation_year_ah!) + 6)
      .attr('y', (_d, i) => (yScale(i) ?? 0) + yScale.bandwidth() / 2)
      .attr('dominant-baseline', 'central')
      .style('font-size', '11px')
      .style('fill', 'var(--color-muted-foreground)')
      .text((d) => `${d.compilation_year_ah} AH`)
  }, [sorted, navigate])

  if (sorted.length === 0) return null

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="text-lg">{t('timeline.collectionDatesTitle')}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground mb-4">
          {t('timeline.collectionDatesBody')}
        </p>
        <div style={{ overflowX: 'auto' }}>
          <svg
            ref={svgRef}
            width="100%"
            height={300}
            role="img"
            aria-label={t('timeline.collectionChartAria')}
          />
        </div>
      </CardContent>
    </Card>
  )
}

function NarratorLanes({ range }: { range: [number, number] }) {
  const { t } = useTranslation()
  const svgRef = useRef<SVGSVGElement | null>(null)
  const navigate = useNavigate()

  const { data } = useQuery({
    queryKey: ['timeline-narrators', range[0], range[1]],
    queryFn: () => fetchNarratorTimeline(range[0], range[1]),
    staleTime: 5 * 60 * 1000,
  })

  const narrators = data?.entries ?? []

  useEffect(() => {
    if (!svgRef.current) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    if (narrators.length === 0) {
      svg.attr('height', 0)
      return
    }

    const width = svgRef.current.clientWidth || 800
    const height = Math.max(200, narrators.length * 30 + MARGIN.top + MARGIN.bottom)
    svg.attr('height', height)

    const xMin = d3.min(narrators, (n) => n.window_start_ah) ?? 0
    const xMax = d3.max(narrators, (n) => n.window_end_ah) ?? 300

    const xScale = d3
      .scaleLinear()
      .domain([xMin - 10, xMax + 10])
      .range([MARGIN.left, width - MARGIN.right])

    const yScale = d3
      .scaleBand<number>()
      .domain(narrators.map((_n, i) => i))
      .range([MARGIN.top, height - MARGIN.bottom])
      .padding(0.3)

    svg
      .append('g')
      .attr('transform', `translate(0,${height - MARGIN.bottom})`)
      .call(d3.axisBottom(xScale).tickFormat((d) => `${d} AH`))
      .selectAll('text')
      .style('font-size', '11px')

    const groups = svg
      .selectAll<SVGGElement, NarratorTimelineEntry>('.narrator-lane')
      .data(narrators)
      .enter()
      .append('g')
      .attr('class', 'narrator-lane')
      .style('cursor', 'pointer')
      .on('click', (_event, d) => navigate(`/narrators/${d.narrator_id}`))

    groups
      .append('rect')
      .attr('x', (d) => xScale(d.window_start_ah))
      .attr('y', (_d, i) => yScale(i) ?? 0)
      .attr('width', (d) => Math.max(4, xScale(d.window_end_ah) - xScale(d.window_start_ah)))
      .attr('height', yScale.bandwidth())
      .attr('rx', 3)
      .attr('fill', (d) =>
        d.estimated ? 'var(--color-muted-foreground)' : 'var(--color-primary)',
      )
      .attr('opacity', (d) => (d.estimated ? 0.45 : 0.75))
      .attr('stroke', (d) => (d.estimated ? 'var(--color-muted-foreground)' : 'none'))
      .attr('stroke-dasharray', (d) => (d.estimated ? '4 2' : 'none'))

    groups
      .append('text')
      .attr('x', MARGIN.left - 8)
      .attr('y', (_d, i) => (yScale(i) ?? 0) + yScale.bandwidth() / 2)
      .attr('text-anchor', 'end')
      .attr('dominant-baseline', 'central')
      .style('font-size', '12px')
      .style('fill', 'var(--color-foreground)')
      .text((d) => d.name_en || d.name_ar || d.narrator_id)

    groups
      .append('text')
      .attr('x', (d) => xScale(d.window_end_ah) + 6)
      .attr('y', (_d, i) => (yScale(i) ?? 0) + yScale.bandwidth() / 2)
      .attr('dominant-baseline', 'central')
      .style('font-size', '11px')
      .style('fill', 'var(--color-muted-foreground)')
      .text((d) => {
        const parts: string[] = []
        if (d.tabaqat_class) parts.push(t('timeline.tabaqaLabel', { class: d.tabaqat_class }))
        if (d.estimated) parts.push(t('timeline.estimatedLabel'))
        return parts.join(' \u00b7 ')
      })
  }, [narrators, navigate, t])

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="text-lg">{t('timeline.narratorLanesTitle')}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground mb-4">{t('timeline.narratorLanesBody')}</p>
        {narrators.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t('timeline.narratorLanesEmpty')}</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <svg
              ref={svgRef}
              width="100%"
              height={200}
              role="img"
              aria-label={t('timeline.narratorChartAria')}
            />
          </div>
        )}
      </CardContent>
    </Card>
  )
}

const EVENT_MARGIN = { top: 30, right: 30, bottom: 40, left: 60 }

export default function TimelinePage() {
  const { t } = useTranslation()
  const svgRef = useRef<SVGSVGElement | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<TimelineEntry | null>(null)
  const [yearRange, setYearRange] = useState<[number, number] | null>(null)

  const { data: rangeData } = useQuery({
    queryKey: ['timeline-range'],
    queryFn: fetchTimelineRange,
    staleTime: 5 * 60 * 1000,
  })

  const { data: collectionsData } = useQuery({
    queryKey: ['collections'],
    queryFn: () => fetchCollections(1, 100),
    staleTime: 5 * 60 * 1000,
  })

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
      svg.attr('height', 0)
      svg.selectAll('.x-axis').remove()
      svg.selectAll('.event-bar').remove()
      return
    }

    const height = Math.max(400, events.length * 30 + EVENT_MARGIN.top + EVENT_MARGIN.bottom)
    svg.attr('height', height)

    const allYears = events.flatMap((e) => [e.year_ah, e.end_year_ah ?? e.year_ah])
    const xMin = d3.min(allYears) ?? 0
    const xMax = d3.max(allYears) ?? 300

    const xScale = d3
      .scaleLinear()
      .domain([xMin - 10, xMax + 10])
      .range([EVENT_MARGIN.left, width - EVENT_MARGIN.right])

    const yScale = d3
      .scaleBand<number>()
      .domain(events.map((_e, i) => i))
      .range([EVENT_MARGIN.top, height - EVENT_MARGIN.bottom])
      .padding(0.3)

    let axisG = svg.selectAll<SVGGElement, null>('.x-axis').data([null])
    axisG = axisG
      .enter()
      .append('g')
      .attr('class', 'x-axis')
      .merge(axisG)

    axisG
      .attr('transform', `translate(0,${height - EVENT_MARGIN.bottom})`)
      .call(d3.axisBottom(xScale).tickFormat((d) => `${d} AH`))
      .selectAll('text')
      .style('font-size', '11px')

    const barGroups = svg
      .selectAll<SVGGElement, TimelineEntry>('.event-bar')
      .data(events, (d) => d.id)

    barGroups.exit().remove()

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

  const hasEvents = events && events.length > 0
  const hasCollections = collectionsData && collectionsData.items.length > 0

  return (
    <div>
      <h2 className="page-heading">{t('timeline.heading')}</h2>
      <p className="muted-text" style={{ marginBottom: 'var(--spacing-4)' }}>
        {t('timeline.intro')}
      </p>

      {hasCollections && <CollectionTimeline collections={collectionsData.items} />}

      <NarratorLanes range={effectiveRange} />

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">{t('timeline.eventsTitle')}</CardTitle>
        </CardHeader>
        <CardContent>
          {hasEvents && (
            <div className="timeline-controls" style={{ marginBottom: 'var(--spacing-4)' }}>
              <label>
                {t('timeline.fromAh')}{' '}
                <input
                  type="number"
                  value={effectiveRange[0]}
                  onChange={(e) => setYearRange([Number(e.target.value), effectiveRange[1]])}
                  className="form-input-sm"
                />
              </label>
              <label>
                {t('timeline.toAh')}{' '}
                <input
                  type="number"
                  value={effectiveRange[1]}
                  onChange={(e) => setYearRange([effectiveRange[0], Number(e.target.value)])}
                  className="form-input-sm"
                />
              </label>
            </div>
          )}

          {isLoading && (
            <div>
              {[1, 2, 3].map((i) => (
                <div key={i} className="skeleton skeleton-row" style={{ width: `${80 - i * 10}%` }} />
              ))}
            </div>
          )}
          {error && <p className="error-text">{t('common.error', { message: (error as Error).message })}</p>}

          {!isLoading && !error && !hasEvents && (
            <div className="empty-state">
              <div className="empty-state-icon">
                <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
              </div>
              <h3 className="empty-state-heading">{t('timeline.noEventsHeading')}</h3>
              <p className="empty-state-body">
                {t('timeline.noEventsBody')}
              </p>
            </div>
          )}

          {hasEvents && (
            <div className="timeline-body">
              <div className="timeline-chart">
                <svg ref={svgRef} width="100%" height={400} role="img" aria-label={t('timeline.chartAria', { from: effectiveRange[0], to: effectiveRange[1] })} />
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
                      {t('timeline.activeNarrators', { count: selectedEvent.narrator_count })}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
