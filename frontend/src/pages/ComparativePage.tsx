import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { fetchParallelPairs, fetchHadith, searchAll } from '../api/client'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Badge } from '../components/ui/Badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/Tabs'

function HadithSearchSelect({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (id: string) => void
}) {
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
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-sm py-1 px-3">
            {value}
          </Badge>
          <Button variant="ghost" size="sm" onClick={() => onChange('')}>
            Clear
          </Button>
        </div>
      ) : (
        <>
          <Input
            placeholder="Search by hadith text or ID..."
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
                  <span className="font-medium">{r.id}</span>
                  <br />
                  <small className="text-muted-foreground">{r.title}</small>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function ComparisonView({ idA, idB }: { idA: string; idB: string }) {
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

  if (loadingA || loadingB) {
    return (
      <div>
        {[1, 2, 3].map((i) => (
          <div key={i} className="skeleton skeleton-row" style={{ width: `${80 - i * 10}%` }} />
        ))}
      </div>
    )
  }

  if (!hadithA || !hadithB) {
    return <p className="error-text">One or both hadiths could not be found.</p>
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {[hadithA, hadithB].map((h) => (
        <Card key={h.id}>
          <CardHeader>
            <CardTitle className="text-base">
              {h.source_corpus} &mdash; {h.id}
            </CardTitle>
            {h.grade_composite && (
              <Badge variant={h.grade_composite.toLowerCase() === 'sahih' ? 'sahih' : 'outline'}>
                {h.grade_composite}
              </Badge>
            )}
          </CardHeader>
          <CardContent>
            <div
              dir="rtl"
              lang="ar"
              className="font-arabic text-base leading-[1.8] mb-4 p-3 rounded-md bg-muted/30"
            >
              {h.isnad_raw_ar && (
                <span className="text-muted-foreground">{h.isnad_raw_ar} </span>
              )}
              {h.matn_ar}
            </div>
            {h.matn_en && (
              <>
                <hr className="border-border my-3" />
                <div className="text-sm leading-relaxed">
                  {h.isnad_raw_en && (
                    <span className="text-muted-foreground">{h.isnad_raw_en} </span>
                  )}
                  {h.matn_en}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

export default function ComparativePage() {
  const [page, setPage] = useState(1)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const compareA = searchParams.get('a') ?? ''
  const compareB = searchParams.get('b') ?? ''

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

  const { data, isLoading, error } = useQuery({
    queryKey: ['parallel-pairs', page],
    queryFn: () => fetchParallelPairs(page, 20),
  })

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0
  const hasParallels = data && data.items.length > 0
  const hasComparison = compareA && compareB

  return (
    <div>
      <h2 className="page-heading">Comparative Analysis</h2>
      <p className="muted-text" style={{ marginBottom: 'var(--spacing-4)' }}>
        Compare hadith texts side by side and browse cross-sectarian parallel pairs.
      </p>

      <Tabs defaultValue={hasComparison ? 'compare' : 'browse'}>
        <TabsList>
          <TabsTrigger value="browse">Browse Parallels</TabsTrigger>
          <TabsTrigger value="compare">Compare Hadiths</TabsTrigger>
        </TabsList>

        <TabsContent value="compare">
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg">Select Hadiths to Compare</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col sm:flex-row gap-4 mb-6">
                <HadithSearchSelect
                  label="First hadith"
                  value={compareA}
                  onChange={(id) => setCompare('a', id)}
                />
                <HadithSearchSelect
                  label="Second hadith"
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
                  <h3 className="empty-state-heading">Select two hadiths to compare</h3>
                  <p className="empty-state-body">
                    Search for hadiths above and select one for each side to view
                    them side by side with their Arabic text, translations, and grades.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="browse">
          {isLoading && (
            <div>
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="skeleton skeleton-row" style={{ width: `${90 - i * 5}%` }} />
              ))}
            </div>
          )}
          {error && <p className="error-text">Error: {(error as Error).message}</p>}

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
              <h3 className="empty-state-heading">No parallel hadith pairs yet</h3>
              <p className="empty-state-body">
                Cross-sectarian parallel hadith pairs will appear here once the deduplication
                pipeline has identified matching texts across Sunni and Shia collections.
                You can still compare individual hadiths using the Compare tab.
              </p>
            </div>
          )}

          {hasParallels && (
            <>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Hadith A</th>
                    <th>Hadith B</th>
                    <th>Similarity</th>
                    <th>Variant Type</th>
                    <th>Cross-Sect</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((pair, idx) => (
                    <tr key={`${pair.hadith_a_id}-${pair.hadith_b_id}-${idx}`}>
                      <td
                        style={{ cursor: 'pointer', color: 'var(--color-primary)' }}
                        onClick={() => navigate(`/hadiths/${pair.hadith_a_id}`)}
                      >
                        <span className="font-medium">{pair.hadith_a_id}</span>
                        <br />
                        <small className="text-muted-foreground">{pair.hadith_a_corpus}</small>
                      </td>
                      <td
                        style={{ cursor: 'pointer', color: 'var(--color-primary)' }}
                        onClick={() => navigate(`/hadiths/${pair.hadith_b_id}`)}
                      >
                        <span className="font-medium">{pair.hadith_b_id}</span>
                        <br />
                        <small className="text-muted-foreground">{pair.hadith_b_corpus}</small>
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
                      <td>{pair.cross_sect ? 'Yes' : 'No'}</td>
                      <td>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setSearchParams({ a: pair.hadith_a_id, b: pair.hadith_b_id })
                          }}
                        >
                          Compare
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="pagination">
                <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                  Previous
                </button>
                <span>
                  Page {data.page} of {totalPages}
                </span>
                <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                  Next
                </button>
              </div>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
