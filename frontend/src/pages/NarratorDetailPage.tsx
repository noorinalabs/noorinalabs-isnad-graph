import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchNarrator, fetchNarratorChains, fetchGraphNetwork } from '../api/client'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'

const RATING_SCALE = ['Thiqah', 'Saduq', 'Maqbul', "Da'if", 'Matruk', 'Kadhdhab']

function ratingColor(rating: string | null): string {
  if (!rating) return 'text-muted-foreground'
  const lower = rating.toLowerCase()
  if (lower === 'thiqah' || lower === 'saduq') return 'text-sahih'
  if (lower === 'maqbul') return 'text-warning'
  return 'text-destructive'
}

function ratingScore(rating: string | null): number {
  if (!rating) return 0
  const idx = RATING_SCALE.findIndex((r) => r.toLowerCase() === rating.toLowerCase())
  if (idx === -1) return 3
  return ((RATING_SCALE.length - idx) / RATING_SCALE.length) * 5
}

export default function NarratorDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [hadithPage, setHadithPage] = useState(1)

  const {
    data: narrator,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['narrator', id],
    queryFn: () => fetchNarrator(id!),
    enabled: !!id,
  })

  const { data: chainsData } = useQuery({
    queryKey: ['narrator-chains', id],
    queryFn: () => fetchNarratorChains(id!),
    enabled: !!id,
  })

  const { data: networkData } = useQuery({
    queryKey: ['narrator-network', id],
    queryFn: () => fetchGraphNetwork(id!, 1),
    enabled: !!id,
  })

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto space-y-4">
        <div className="h-6 bg-muted rounded w-48 animate-pulse" />
        <Card className="animate-pulse">
          <CardContent className="py-8">
            <div className="h-8 bg-muted rounded w-1/3 mb-4" />
            <div className="h-6 bg-muted rounded w-1/4 mb-6" />
            <div className="space-y-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-4 bg-muted rounded w-1/2" />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-5xl mx-auto">
        <p className="text-destructive">Error: {(error as Error).message}</p>
      </div>
    )
  }

  if (!narrator) {
    return (
      <div className="max-w-5xl mx-auto">
        <p>Narrator not found.</p>
      </div>
    )
  }

  const score = ratingScore(narrator.trustworthiness_consensus)
  const scorePercent = (score / 5) * 100

  const profileFields: [string, string | null][] = [
    ['Full name', narrator.name_en],
    ['Kunya', narrator.kunya],
    ['Nisba', narrator.nisba],
    ['Laqab', narrator.laqab],
    ['Generation', narrator.generation],
    ['Birth', narrator.birth_year_ah != null ? `${narrator.birth_year_ah} AH` : null],
    ['Death', narrator.death_year_ah != null ? `${narrator.death_year_ah} AH` : null],
    ['Gender', narrator.gender],
    ['Sect', narrator.sect_affiliation],
  ]

  const hadithsPerPage = 10
  const chains = chainsData?.chains ?? []
  const totalHadithPages = Math.ceil(chains.length / hadithsPerPage)
  const paginatedChains = chains.slice(
    (hadithPage - 1) * hadithsPerPage,
    hadithPage * hadithsPerPage,
  )

  return (
    <div className="max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <nav className="mb-4 text-sm text-muted-foreground">
        <Link to="/narrators" className="hover:text-foreground">
          Narrators
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-foreground">{narrator.name_en || narrator.name_ar}</span>
      </nav>

      {/* Profile card */}
      <Card className="mb-6" aria-label={`Narrator profile: ${narrator.name_en || narrator.name_ar}`}>
        <CardContent className="py-6">
          <div className="flex flex-col lg:flex-row gap-6">
            {/* Biography section */}
            <div className="flex-1">
              {/* Name */}
              <div dir="rtl" lang="ar" className="text-[28px] font-arabic leading-relaxed mb-1">
                {narrator.name_ar}
              </div>
              {narrator.name_en && (
                <div className="text-xl text-muted-foreground mb-4">{narrator.name_en}</div>
              )}

              {/* Metadata grid */}
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
                {profileFields.map(([label, value]) => (
                  <div key={label} className="contents">
                    <dt className="font-semibold text-muted-foreground">{label}</dt>
                    <dd>{value ?? <span className="text-muted-foreground">&mdash;</span>}</dd>
                  </div>
                ))}
              </dl>
            </div>

            {/* Network preview placeholder */}
            <div className="lg:w-[400px] shrink-0">
              <Card className="bg-muted/30 h-full min-h-[250px]">
                <CardContent className="py-4 h-full flex flex-col">
                  <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
                    {networkData ? (
                      <div className="text-center">
                        <div className="text-4xl mb-2" aria-hidden="true">
                          &#9679;
                        </div>
                        <p aria-label={`Transmission network preview showing ${networkData.teachers} teachers and ${networkData.students} students`}>
                          {networkData.nodes.length} nodes in ego-graph
                        </p>
                      </div>
                    ) : (
                      'Loading network...'
                    )}
                  </div>
                  <div className="flex justify-between items-center text-sm mt-2">
                    <span>
                      Teachers: {networkData?.teachers ?? '...'} | Students:{' '}
                      {networkData?.students ?? '...'}
                    </span>
                    <Link
                      to={`/graph?narrator=${id}`}
                      className="text-primary hover:underline text-sm"
                    >
                      Open in Graph Explorer
                    </Link>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Reliability ratings */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">Reliability Ratings</CardTitle>
        </CardHeader>
        <CardContent>
          {/* Aggregate bar */}
          <div className="mb-4">
            <div className="flex items-center justify-between mb-1">
              <span className={`font-semibold ${ratingColor(narrator.trustworthiness_consensus)}`}>
                Aggregate: {narrator.trustworthiness_consensus ?? 'Unknown'}
              </span>
              <span className="text-sm text-muted-foreground">
                {score.toFixed(1)}/5.0
              </span>
            </div>
            <div className="w-full h-2 bg-muted rounded-full overflow-hidden" role="progressbar" aria-valuenow={score} aria-valuemin={0} aria-valuemax={5} aria-label={`Trustworthiness rating: ${score.toFixed(1)} out of 5`}>
              <div
                className={`h-full rounded-full transition-all ${
                  score >= 4 ? 'bg-sahih' : score >= 3 ? 'bg-warning' : 'bg-destructive'
                }`}
                style={{ width: `${scorePercent}%` }}
              />
            </div>
          </div>

          {/* Rating scale legend */}
          <p className="text-xs text-muted-foreground">
            Rating scale: {RATING_SCALE.join(' > ')}
          </p>
        </CardContent>
      </Card>

      {/* Network statistics */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">Network Statistics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {[
              ['Teachers (in-degree)', narrator.in_degree, 'Number of narrators who transmitted to this narrator'],
              ['Students (out-degree)', narrator.out_degree, 'Number of narrators this narrator transmitted to'],
              ['Total connections', narrator.in_degree != null && narrator.out_degree != null ? narrator.in_degree + narrator.out_degree : null, 'Combined in-degree and out-degree'],
              ['Betweenness', narrator.betweenness_centrality?.toFixed(4), 'How often this narrator appears on shortest paths between other narrators'],
              ['PageRank', narrator.pagerank?.toFixed(4), 'Importance based on the importance of connected narrators'],
              ['Community', narrator.community_id != null ? `#${narrator.community_id}` : null, 'Transmission community cluster'],
            ].map(
              ([label, value, tooltip]) =>
                value != null && (
                  <div
                    key={label as string}
                    className="p-3 border rounded-md text-center"
                    title={tooltip as string}
                  >
                    <div className="text-xs text-muted-foreground mb-1">{label as string}</div>
                    <div className="text-lg font-semibold">{value as string | number}</div>
                  </div>
                ),
            )}
          </div>
        </CardContent>
      </Card>

      {/* Hadith list */}
      {chains.length > 0 && (
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">
                Hadith Narrated ({chainsData?.total ?? chains.length} total)
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {paginatedChains.map((chain) => (
                <Link
                  key={chain.chain_id}
                  to={`/hadiths/${chain.hadith_id}`}
                  className="block"
                >
                  <Card className="hover:shadow-md transition-shadow">
                    <CardContent className="py-3">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-sm">
                          Hadith {chain.hadith_id}
                        </span>
                        {chain.grade && (
                          <Badge
                            variant={chain.grade.toLowerCase() === 'sahih' ? 'sahih' : 'outline'}
                            className="text-xs"
                          >
                            {chain.grade}
                          </Badge>
                        )}
                      </div>
                      {chain.matn_ar && (
                        <div
                          dir="rtl"
                          lang="ar"
                          className="text-sm text-muted-foreground font-arabic line-clamp-2 leading-relaxed"
                        >
                          {chain.matn_ar}
                        </div>
                      )}
                      {chain.matn_en && (
                        <div className="text-sm text-muted-foreground line-clamp-1 mt-1">
                          {chain.matn_en}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>

            {/* Pagination */}
            {totalHadithPages > 1 && (
              <nav
                aria-label="Hadith list pagination"
                className="flex items-center justify-center gap-1 mt-4"
              >
                <Button
                  variant="outline"
                  size="sm"
                  disabled={hadithPage <= 1}
                  onClick={() => setHadithPage((p) => p - 1)}
                >
                  Prev
                </Button>
                <span className="text-sm text-muted-foreground px-2">
                  {hadithPage} of {totalHadithPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={hadithPage >= totalHadithPages}
                  onClick={() => setHadithPage((p) => p + 1)}
                >
                  Next
                </Button>
              </nav>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
