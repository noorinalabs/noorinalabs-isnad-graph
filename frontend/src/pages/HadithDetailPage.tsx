import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchHadith, fetchHadithParallels } from '../api/client'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'

function gradeColor(grade: string | null): string {
  if (!grade) return ''
  const lower = grade.toLowerCase()
  if (lower === 'sahih') return 'bg-sahih-bg text-sahih'
  if (lower === 'hasan') return 'bg-hasan-bg text-hasan'
  if (lower === "da'if" || lower === 'daif') return 'bg-daif-bg text-daif'
  if (lower === "mawdu'" || lower === 'mawdu') return 'bg-mawdu-bg text-mawdu'
  return ''
}

function gradeBarColor(grade: string | null): string {
  if (!grade) return 'bg-muted'
  const lower = grade.toLowerCase()
  if (lower === 'sahih') return 'bg-sahih'
  if (lower === 'hasan') return 'bg-hasan'
  if (lower === "da'if" || lower === 'daif') return 'bg-warning'
  if (lower === "mawdu'" || lower === 'mawdu') return 'bg-destructive'
  return 'bg-muted'
}

function similarityLevel(score: number): string {
  if (score >= 0.9) return 'text-sahih'
  if (score >= 0.7) return 'text-warning'
  return 'text-muted-foreground'
}

export default function HadithDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [copiedField, setCopiedField] = useState<string | null>(null)

  const {
    data: hadith,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['hadith', id],
    queryFn: () => fetchHadith(id!),
    enabled: !!id,
  })

  const { data: parallelsData } = useQuery({
    queryKey: ['hadith-parallels', id],
    queryFn: () => fetchHadithParallels(id!),
    enabled: !!id,
  })

  const copyToClipboard = async (text: string, field: string) => {
    await navigator.clipboard.writeText(text)
    setCopiedField(field)
    setTimeout(() => setCopiedField(null), 2000)
  }

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto space-y-4">
        <div className="h-6 bg-muted rounded w-48 animate-pulse" />
        <Card className="animate-pulse">
          <CardContent className="py-8">
            <div className="h-8 bg-muted rounded w-1/2 mb-6" />
            <div className="space-y-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-5 bg-muted rounded w-full" />
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

  if (!hadith) {
    return (
      <div className="max-w-5xl mx-auto">
        <p>Hadith not found.</p>
      </div>
    )
  }

  const parallels = parallelsData?.parallels ?? []
  const citation = `${hadith.source_corpus}, Hadith ${hadith.id}.`

  return (
    <div className="max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <nav className="mb-4 text-sm text-muted-foreground">
        <Link to="/hadiths" className="hover:text-foreground">
          Hadiths
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-foreground">
          {hadith.source_corpus} &mdash; {hadith.id}
        </span>
      </nav>

      {/* Hadith text section */}
      <Card className="mb-6" aria-label="Hadith text">
        <CardContent className="py-6">
          <div className="flex items-center gap-3 mb-4">
            <h2 className="text-xl font-semibold">
              {hadith.source_corpus} &mdash; {hadith.id}
            </h2>
            {hadith.grade_composite && (
              <span
                className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold ${gradeColor(hadith.grade_composite)}`}
              >
                {hadith.grade_composite}
              </span>
            )}
          </div>

          {/* Arabic matn */}
          <div
            dir="rtl"
            lang="ar"
            className="font-arabic text-lg leading-[1.8] mb-4 p-4 rounded-md bg-muted/30"
            style={{ color: 'var(--color-foreground)' }}
          >
            {hadith.isnad_raw_ar && (
              <span style={{ color: 'var(--color-muted-foreground)' }}>{hadith.isnad_raw_ar} </span>
            )}
            {hadith.matn_ar}
          </div>

          {/* Divider */}
          <hr className="border-border my-4" />

          {/* English translation */}
          {hadith.matn_en && (
            <div className="leading-relaxed text-base">
              {hadith.isnad_raw_en && (
                <span className="text-muted-foreground">{hadith.isnad_raw_en} </span>
              )}
              {hadith.matn_en}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Isnad chain + Grading side by side on desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6 mb-6">
        {/* Isnad chain visualization placeholder */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Isnad Chain</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center min-h-[200px] text-muted-foreground text-sm border rounded-md bg-muted/30 p-4">
              <div className="text-center">
                <p className="mb-2">Chain visualization placeholder</p>
                <p className="text-xs">
                  Chain data will be rendered here when available
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Grading and metadata panel */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Grading</CardTitle>
          </CardHeader>
          <CardContent>
            {/* Grade bar */}
            {hadith.grade_composite && (
              <div className="mb-4">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-semibold">
                    Primary Grade: {hadith.grade_composite}
                  </span>
                </div>
                <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${gradeBarColor(hadith.grade_composite)}`}
                    style={{
                      width:
                        hadith.grade_composite.toLowerCase() === 'sahih'
                          ? '100%'
                          : hadith.grade_composite.toLowerCase() === 'hasan'
                            ? '75%'
                            : '40%',
                    }}
                  />
                </div>
              </div>
            )}

            {/* Metadata */}
            <div className="mt-4">
              <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                Metadata
              </h4>
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
                <dt className="font-medium text-muted-foreground">Collection</dt>
                <dd>{hadith.source_corpus}</dd>
                <dt className="font-medium text-muted-foreground">Hadith No.</dt>
                <dd>{hadith.id}</dd>
                {hadith.has_sunni_parallel && (
                  <>
                    <dt className="font-medium text-muted-foreground">Sunni parallel</dt>
                    <dd>Yes</dd>
                  </>
                )}
                {hadith.has_shia_parallel && (
                  <>
                    <dt className="font-medium text-muted-foreground">Shia parallel</dt>
                    <dd>Yes</dd>
                  </>
                )}
              </dl>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Topics */}
      {hadith.topic_tags && hadith.topic_tags.length > 0 && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">Topics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {hadith.topic_tags.map((tag) => (
                <Link key={tag} to={`/search?q=${encodeURIComponent(tag)}`}>
                  <Badge variant="secondary" className="cursor-pointer hover:bg-secondary/80">
                    {tag}
                  </Badge>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Parallel hadith */}
      {parallels.length > 0 && (
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">
                Parallel Hadith ({parallelsData?.total ?? parallels.length} found)
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3" aria-label={`${parallels.length} parallel hadith found`}>
              {parallels.map((p) => (
                <Link key={p.id} to={`/hadiths/${p.id}`} className="block">
                  <Card className="hover:shadow-md transition-shadow">
                    <CardContent className="py-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-sm">{p.source_corpus}</span>
                        {p.similarity_score != null && (
                          <span className={`text-xs font-medium ${similarityLevel(p.similarity_score)}`}>
                            Similarity: {(p.similarity_score * 100).toFixed(0)}%
                          </span>
                        )}
                      </div>
                      <div
                        dir="rtl"
                        lang="ar"
                        className="text-sm font-arabic line-clamp-2 leading-relaxed text-muted-foreground mb-1"
                      >
                        {p.matn_ar}
                      </div>
                      {p.matn_en && (
                        <div className="text-sm text-muted-foreground line-clamp-1">
                          {p.matn_en}
                        </div>
                      )}
                      <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                        {p.grade && (
                          <Badge
                            variant={p.grade.toLowerCase() === 'sahih' ? 'sahih' : 'outline'}
                            className="text-xs"
                          >
                            {p.grade}
                          </Badge>
                        )}
                        {p.cross_sect && (
                          <Badge variant="outline" className="text-xs">
                            Cross-sect
                          </Badge>
                        )}
                        <Link
                          to={`/compare?a=${id}&b=${p.id}`}
                          className="text-primary hover:underline ms-auto"
                          onClick={(e) => e.stopPropagation()}
                        >
                          Compare
                        </Link>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Citation & Share */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">Citation</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm mb-3">{citation}</p>
          <div className="flex flex-wrap gap-2" aria-live="polite">
            <Button
              variant="outline"
              size="sm"
              onClick={() => copyToClipboard(citation, 'citation')}
            >
              {copiedField === 'citation' ? 'Copied!' : 'Copy citation'}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => copyToClipboard(hadith.matn_ar, 'arabic')}
            >
              {copiedField === 'arabic' ? 'Copied!' : 'Copy Arabic text'}
            </Button>
            {hadith.matn_en && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => copyToClipboard(hadith.matn_en!, 'translation')}
              >
                {copiedField === 'translation' ? 'Copied!' : 'Copy translation'}
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => copyToClipboard(window.location.href, 'share')}
            >
              {copiedField === 'share' ? 'Copied!' : 'Share'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
