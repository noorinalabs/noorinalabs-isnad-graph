import { useState, useCallback, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  fetchParallelPairs,
  fetchHadith,
  fetchHadithParallels,
  searchAll,
} from '../api/client'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Badge } from '../components/ui/Badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/Tabs'
import { gradeColor } from '../lib/grades'
import { diffTokens, type DiffToken } from '../lib/textDiff'
import type { Hadith } from '../types/api'

function corpusLabel(corpus: string): string {
  if (!corpus) return ''
  return corpus.charAt(0).toUpperCase() + corpus.slice(1)
}

// Render a token stream with divergent tokens highlighted; shared tokens render
// plainly so agreement reads as the calm baseline and differences draw the eye.
function DiffText({
  tokens,
  dir,
  lang,
  className,
}: {
  tokens: DiffToken[]
  dir?: 'rtl' | 'ltr'
  lang?: string
  className?: string
}) {
  return (
    <span dir={dir} lang={lang} className={className}>
      {tokens.map((t, i) => (
        <span key={i} className={t.shared ? undefined : 'diff-unique'}>
          {t.text}
          {i < tokens.length - 1 ? ' ' : ''}
        </span>
      ))}
    </span>
  )
}

function GradePill({ hadith }: { hadith: Hadith }) {
  if (!hadith.grade_composite) return null
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${gradeColor(hadith.grade_normalized)}`}
    >
      {hadith.grade_composite}
    </span>
  )
}

// Selected-hadith chip: shows the human-readable title + matn preview + grade
// (fetched by ID), instead of an opaque raw-ID badge. (#1037)
function HadithChip({ id, onClear }: { id: string; onClear: () => void }) {
  const { t } = useTranslation()
  const { data, isLoading } = useQuery({
    queryKey: ['hadith', id],
    queryFn: () => fetchHadith(id),
    enabled: !!id,
  })

  return (
    <div className="flex items-center gap-2 flex-wrap rounded-md border border-border bg-muted/30 p-2">
      <div className="flex flex-col min-w-0">
        <span className="font-medium text-sm">
          {data?.display_title ?? (isLoading ? t('common.loading') : id)}
        </span>
        {data?.matn_en && (
          <small className="text-muted-foreground truncate" style={{ maxWidth: '34ch' }}>
            {data.matn_en}
          </small>
        )}
      </div>
      {data && <GradePill hadith={data} />}
      <Button variant="ghost" size="sm" onClick={onClear}>
        {t('comparative.clear')}
      </Button>
    </div>
  )
}

function HadithSearchSelect({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (id: string) => void
}) {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)

  const { data: results } = useQuery({
    queryKey: ['search-hadiths', query],
    queryFn: () => searchAll(query, 10),
    enabled: query.length >= 2,
    staleTime: 30 * 1000,
  })

  const hadithResults = results?.results.filter((r) => r.type === 'hadith') ?? []

  return (
    <div style={{ position: 'relative', flex: 1 }}>
      <label className="text-sm font-medium text-muted-foreground mb-1 block">{label}</label>
      {value ? (
        <HadithChip id={value} onClear={() => onChange('')} />
      ) : (
        <>
          <Input
            placeholder={t('comparative.searchPlaceholder')}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setOpen(true)
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => setOpen(false)}
          />
          {open && hadithResults.length > 0 && (
            <div className="search-dropdown">
              {hadithResults.map((r) => (
                <div
                  key={r.id}
                  className="search-dropdown-item"
                  onPointerDown={(e) => {
                    e.preventDefault()
                    onChange(r.id)
                    setQuery('')
                    setOpen(false)
                  }}
                >
                  {/* Lead with readable title; keep the ID as secondary metadata. */}
                  <span className="font-medium">{r.title || r.id}</span>
                  {r.collection && (
                    <span className="text-muted-foreground text-xs"> · {r.collection}</span>
                  )}
                  <br />
                  <small className="text-muted-foreground">{r.id}</small>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function AnalysisStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="analysis-stat">
      <span className="analysis-stat-label">{label}</span>
      <span className="analysis-stat-value">{value}</span>
    </div>
  )
}

type SideDiffs = {
  matnAr: DiffToken[]
  matnEn: DiffToken[] | null
  isnadAr: DiffToken[] | null
  isnadEn: DiffToken[] | null
}

function ComparisonCard({ hadith, diffs }: { hadith: Hadith; diffs: SideDiffs }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{hadith.display_title ?? hadith.id}</CardTitle>
        <div className="flex flex-wrap items-center gap-2 mt-1">
          <Badge variant="secondary">{corpusLabel(hadith.source_corpus)}</Badge>
          {hadith.collection_name && (
            <span className="text-xs text-muted-foreground">{hadith.collection_name}</span>
          )}
          <GradePill hadith={hadith} />
        </div>
      </CardHeader>
      <CardContent>
        {diffs.isnadAr && (
          <div
            dir="rtl"
            lang="ar"
            className="font-arabic text-sm leading-[1.8] mb-1 text-muted-foreground"
          >
            <DiffText tokens={diffs.isnadAr} dir="rtl" lang="ar" />
          </div>
        )}
        <div
          dir="rtl"
          lang="ar"
          className="font-arabic text-base leading-[1.8] mb-4 p-3 rounded-md bg-muted/30"
        >
          <DiffText tokens={diffs.matnAr} dir="rtl" lang="ar" />
        </div>

        {(diffs.matnEn || diffs.isnadEn) && (
          <>
            <hr className="border-border my-3" />
            <div className="text-sm leading-relaxed">
              {diffs.isnadEn && (
                <DiffText tokens={diffs.isnadEn} className="text-muted-foreground" />
              )}{' '}
              {diffs.matnEn && <DiffText tokens={diffs.matnEn} />}
            </div>
          </>
        )}

        {hadith.topic_tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-3">
            {hadith.topic_tags.map((tag) => (
              <Badge key={tag} variant="outline" className="text-xs">
                {tag}
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ComparisonView({ idA, idB }: { idA: string; idB: string }) {
  const { t } = useTranslation()
  const { data: hadithA, isLoading: loadingA } = useQuery({
    queryKey: ['hadith', idA],
    queryFn: () => fetchHadith(idA),
    enabled: !!idA,
  })

  const { data: hadithB, isLoading: loadingB } = useQuery({
    queryKey: ['hadith', idB],
    queryFn: () => fetchHadith(idB),
    enabled: !!idB,
  })

  // The similarity score / variant type live on the PARALLEL_OF edge, so look the
  // pair up via A's parallels. Surfaces the metric even on direct navigation, not
  // only when arriving from a Browse row. (#1037)
  const { data: parallels } = useQuery({
    queryKey: ['hadith-parallels', idA],
    queryFn: () => fetchHadithParallels(idA),
    enabled: !!idA && !!idB,
  })
  const pairMeta = parallels?.parallels.find((p) => p.id === idB)

  const diffs = useMemo(() => {
    if (!hadithA || !hadithB) return null
    const matnAr = diffTokens(hadithA.matn_ar, hadithB.matn_ar)
    const matnEn =
      hadithA.matn_en && hadithB.matn_en
        ? diffTokens(hadithA.matn_en, hadithB.matn_en)
        : null
    const isnadAr =
      hadithA.isnad_raw_ar && hadithB.isnad_raw_ar
        ? diffTokens(hadithA.isnad_raw_ar, hadithB.isnad_raw_ar)
        : null
    const isnadEn =
      hadithA.isnad_raw_en && hadithB.isnad_raw_en
        ? diffTokens(hadithA.isnad_raw_en, hadithB.isnad_raw_en)
        : null
    return { matnAr, matnEn, isnadAr, isnadEn }
  }, [hadithA, hadithB])

  if (loadingA || loadingB) {
    return (
      <div>
        {[1, 2, 3].map((i) => (
          <div key={i} className="skeleton skeleton-row" style={{ width: `${80 - i * 10}%` }} />
        ))}
      </div>
    )
  }

  if (!hadithA || !hadithB || !diffs) {
    return <p className="error-text">{t('comparative.notFoundPair')}</p>
  }

  const matnOverlap = diffs.matnEn?.overlap ?? diffs.matnAr.overlap
  const sharedNarrators = diffs.isnadEn?.sharedCount ?? diffs.isnadAr?.sharedCount ?? null

  const sideA: SideDiffs = {
    matnAr: diffs.matnAr.a,
    matnEn: diffs.matnEn?.a ?? null,
    isnadAr: diffs.isnadAr?.a ?? null,
    isnadEn: diffs.isnadEn?.a ?? null,
  }
  const sideB: SideDiffs = {
    matnAr: diffs.matnAr.b,
    matnEn: diffs.matnEn?.b ?? null,
    isnadAr: diffs.isnadAr?.b ?? null,
    isnadEn: diffs.isnadEn?.b ?? null,
  }

  return (
    <div>
      <div className="analysis-bar" aria-label={t('comparative.comparisonSummary')}>
        <AnalysisStat
          label={t('common.similarity')}
          value={
            pairMeta?.similarity_score != null
              ? `${(pairMeta.similarity_score * 100).toFixed(1)}%`
              : t('comparative.wordOverlap', { percent: Math.round(matnOverlap * 100) })
          }
        />
        {pairMeta?.variant_type && (
          <AnalysisStat label={t('comparative.statVariant')} value={pairMeta.variant_type.replace(/_/g, ' ')} />
        )}
        <AnalysisStat
          label={t('comparative.statSectPairing')}
          value={
            pairMeta
              ? pairMeta.cross_sect
                ? t('common.crossSect')
                : t('common.withinSect')
              : hadithA.source_corpus === hadithB.source_corpus
                ? t('comparative.sameCorpus')
                : t('comparative.differentCorpora')
          }
        />
        {sharedNarrators != null && (
          <AnalysisStat label={t('comparative.statSharedIsnad')} value={String(sharedNarrators)} />
        )}
        {!pairMeta && (
          <span className="text-xs text-muted-foreground">
            {t('comparative.noRecordedLink')}
          </span>
        )}
      </div>

      <div className="diff-legend" aria-hidden="true">
        <span>
          <span className="diff-legend-swatch" style={{ background: 'var(--color-hasan-bg)' }} />
          {t('comparative.legendDiffers')}
        </span>
        <span>{t('comparative.legendShared')}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ComparisonCard hadith={hadithA} diffs={sideA} />
        <ComparisonCard hadith={hadithB} diffs={sideB} />
      </div>
    </div>
  )
}

type SectFilter = 'all' | 'cross' | 'intra'
type SortDir = 'desc' | 'asc'

const SECT_FILTERS: { value: SectFilter; labelKey: string; crossSect?: boolean }[] = [
  { value: 'all', labelKey: 'comparative.sectAll', crossSect: undefined },
  { value: 'intra', labelKey: 'comparative.sectWithin', crossSect: false },
  { value: 'cross', labelKey: 'comparative.sectCross', crossSect: true },
]

export default function ComparativePage() {
  const { t } = useTranslation()
  const [page, setPage] = useState(1)
  const [sectFilter, setSectFilter] = useState<SectFilter>('all')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const compareA = searchParams.get('a') ?? ''
  const compareB = searchParams.get('b') ?? ''
  const hasComparison = Boolean(compareA && compareB)

  // Controlled tabs so the Browse "Compare" button can actually switch the view —
  // an uncontrolled defaultValue only applies on mount, making the button a
  // visual no-op. (#1037)
  const [tab, setTab] = useState<'browse' | 'compare'>(hasComparison ? 'compare' : 'browse')

  const crossSect = SECT_FILTERS.find((f) => f.value === sectFilter)?.crossSect

  const setCompare = useCallback(
    (key: 'a' | 'b', value: string) => {
      const next = new URLSearchParams(searchParams)
      if (value) {
        next.set(key, value)
      } else {
        next.delete(key)
      }
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const compareFromBrowse = useCallback(
    (aId: string, bId: string) => {
      setSearchParams({ a: aId, b: bId })
      setTab('compare')
    },
    [setSearchParams],
  )

  const { data, isLoading, error } = useQuery({
    queryKey: ['parallel-pairs', page, sectFilter],
    queryFn: () => fetchParallelPairs(page, 20, crossSect),
  })

  const selectSectFilter = useCallback((value: SectFilter) => {
    setSectFilter(value)
    setPage(1)
  }, [])

  // Client-side sort of the current page by similarity. Nulls sort last either way.
  const sortedItems = useMemo(() => {
    if (!data) return []
    const items = [...data.items]
    items.sort((x, y) => {
      const a = x.similarity_score
      const b = y.similarity_score
      if (a == null && b == null) return 0
      if (a == null) return 1
      if (b == null) return -1
      return sortDir === 'desc' ? b - a : a - b
    })
    return items
  }, [data, sortDir])

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0
  const hasParallels = sortedItems.length > 0

  return (
    <div>
      <h2 className="page-heading">{t('comparative.heading')}</h2>
      <p className="muted-text" style={{ marginBottom: 'var(--spacing-4)' }}>
        {t('comparative.intro')}
      </p>

      <Tabs value={tab} onValueChange={(value) => setTab(value as 'browse' | 'compare')}>
        <TabsList>
          <TabsTrigger value="browse">{t('comparative.tabBrowse')}</TabsTrigger>
          <TabsTrigger value="compare">{t('comparative.tabCompare')}</TabsTrigger>
        </TabsList>

        <TabsContent value="compare">
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg">{t('comparative.selectTitle')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col sm:flex-row gap-4 mb-6">
                <HadithSearchSelect
                  label={t('comparative.firstHadith')}
                  value={compareA}
                  onChange={(id) => setCompare('a', id)}
                />
                <HadithSearchSelect
                  label={t('comparative.secondHadith')}
                  value={compareB}
                  onChange={(id) => setCompare('b', id)}
                />
              </div>

              {hasComparison ? (
                <ComparisonView idA={compareA} idB={compareB} />
              ) : (
                <div className="empty-state">
                  <div className="empty-state-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <rect x="2" y="4" width="8" height="16" rx="1" />
                      <rect x="14" y="4" width="8" height="16" rx="1" />
                      <path d="M10 12h4" />
                    </svg>
                  </div>
                  <h3 className="empty-state-heading">{t('comparative.emptySelectHeading')}</h3>
                  <p className="empty-state-body">
                    {t('comparative.emptySelectBody')}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="browse">
          <div className="flex flex-wrap gap-2 mb-4" role="group" aria-label={t('comparative.filterSectAria')}>
            {SECT_FILTERS.map((f) => (
              <Button
                key={f.value}
                variant={sectFilter === f.value ? 'default' : 'outline'}
                size="sm"
                onClick={() => selectSectFilter(f.value)}
                aria-pressed={sectFilter === f.value}
              >
                {t(f.labelKey)}
              </Button>
            ))}
          </div>

          {isLoading && (
            <div>
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="skeleton skeleton-row" style={{ width: `${90 - i * 5}%` }} />
              ))}
            </div>
          )}
          {error && <p className="error-text">{t('common.error', { message: (error as Error).message })}</p>}

          {!isLoading && !error && !hasParallels && (
            <div className="empty-state">
              <div className="empty-state-icon">
                <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M16 3h5v5" />
                  <path d="M8 3H3v5" />
                  <path d="M12 22v-8.3a4 4 0 0 0-1.172-2.872L3 3" />
                  <path d="m15 9 6-6" />
                </svg>
              </div>
              <h3 className="empty-state-heading">{t('comparative.noParallelsHeading')}</h3>
              <p className="empty-state-body">
                {t('comparative.noParallelsBody')}
              </p>
            </div>
          )}

          {hasParallels && (
            <>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t('comparative.colHadithA')}</th>
                    <th>{t('comparative.colHadithB')}</th>
                    <th
                      className="th-sortable"
                      onClick={() => setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))}
                      role="button"
                      tabIndex={0}
                      aria-sort={sortDir === 'desc' ? 'descending' : 'ascending'}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))
                        }
                      }}
                    >
                      {t('common.similarity')} {sortDir === 'desc' ? '↓' : '↑'}
                    </th>
                    <th>{t('comparative.colVariantType')}</th>
                    <th>{t('comparative.colSectPairing')}</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {sortedItems.map((pair, idx) => (
                    <tr key={`${pair.hadith_a_id}-${pair.hadith_b_id}-${idx}`}>
                      <td
                        style={{ cursor: 'pointer', color: 'var(--color-primary)', maxWidth: '22rem' }}
                        onClick={() => navigate(`/hadiths/${pair.hadith_a_id}`)}
                      >
                        <span className="font-medium">
                          {pair.hadith_a_title || pair.hadith_a_id}
                        </span>
                        <br />
                        <small className="text-muted-foreground">
                          {corpusLabel(pair.hadith_a_corpus)}
                          {pair.hadith_a_snippet ? ` — ${pair.hadith_a_snippet}` : ''}
                        </small>
                      </td>
                      <td
                        style={{ cursor: 'pointer', color: 'var(--color-primary)', maxWidth: '22rem' }}
                        onClick={() => navigate(`/hadiths/${pair.hadith_b_id}`)}
                      >
                        <span className="font-medium">
                          {pair.hadith_b_title || pair.hadith_b_id}
                        </span>
                        <br />
                        <small className="text-muted-foreground">
                          {corpusLabel(pair.hadith_b_corpus)}
                          {pair.hadith_b_snippet ? ` — ${pair.hadith_b_snippet}` : ''}
                        </small>
                      </td>
                      <td>
                        {pair.similarity_score != null ? (
                          <span className={pair.similarity_score > 0.8 ? 'badge-similarity-high' : 'badge-similarity-low'}>
                            {(pair.similarity_score * 100).toFixed(1)}%
                          </span>
                        ) : (
                          '-'
                        )}
                      </td>
                      <td>{pair.variant_type ?? '-'}</td>
                      <td>{pair.cross_sect ? t('common.crossSect') : t('common.withinSect')}</td>
                      <td>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => compareFromBrowse(pair.hadith_a_id, pair.hadith_b_id)}
                        >
                          {t('nav.compare')}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="pagination">
                <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                  {t('common.previous')}
                </button>
                <span>
                  {t('common.pageOf', { current: data?.page, total: totalPages })}
                </span>
                <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                  {t('common.next')}
                </button>
              </div>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
