import { useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { fetchHadith, fetchHadithParallels, fetchHadithChain, fetchHadithDating } from '../api/client'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { gradeColor, gradeBarColor, gradeBarWidth } from '../lib/grades'

function similarityLevel(score: number): string {
  if (score >= 0.9) return 'text-sahih'
  if (score >= 0.7) return 'text-warning'
  return 'text-muted-foreground'
}

export default function HadithDetailPage() {
  const { t } = useTranslation()
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

  const { data: chainData, isLoading: chainLoading } = useQuery({
    queryKey: ['hadith-chain', id],
    queryFn: () => fetchHadithChain(id!),
    enabled: !!id,
  })

  const { data: dating, isLoading: datingLoading } = useQuery({
    queryKey: ['hadith-dating', id],
    queryFn: () => fetchHadithDating(id!),
    enabled: !!id,
  })

  // Flatten the chain (nodes + position-ordered edges) into the transmission
  // sequence Prophet/companion → ... → collector. The API already orders edges
  // by position_in_chain, so the sequence is the first edge's source followed
  // by each edge's target, de-duplicating consecutive repeats.
  const chainNarrators = useMemo(() => {
    if (!chainData || chainData.edges.length === 0) return []
    const byId = new Map(chainData.nodes.map((n) => [n.id, n]))
    const order: string[] = [chainData.edges[0]!.source]
    for (const edge of chainData.edges) order.push(edge.target)
    const seen = new Set<string>()
    return order
      .filter((nid) => {
        if (seen.has(nid)) return false
        seen.add(nid)
        return true
      })
      .map((nid) => byId.get(nid))
      .filter((n): n is NonNullable<typeof n> => n != null)
  }, [chainData])

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
        <p className="text-destructive">{t('common.error', { message: (error as Error).message })}</p>
      </div>
    )
  }

  if (!hadith) {
    return (
      <div className="max-w-5xl mx-auto">
        <p>{t('hadithDetail.notFound')}</p>
      </div>
    )
  }

  const parallels = parallelsData?.parallels ?? []
  const citation = t('hadithDetail.citation', { title: hadith.display_title || hadith.source_corpus, id: hadith.id })
  const shortCitation = t('hadithDetail.shortCitation', { title: hadith.display_title || hadith.source_corpus, id: hadith.id })

  const handleShare = async () => {
    const url = window.location.href
    if (navigator.share) {
      try {
        await navigator.share({
          title: t('hadithDetail.shareTitle', { title: hadith.display_title || hadith.source_corpus, id: hadith.id }),
          text: shortCitation,
          url,
        })
        return
      } catch {
        // User cancelled or Web Share API failed — fall through to clipboard
      }
    }
    await copyToClipboard(url, 'share')
  }

  return (
    <div className="max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <nav className="mb-4 text-sm text-muted-foreground">
        <Link to="/hadiths" className="hover:text-foreground">
          {t('nav.hadiths')}
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-foreground">
          {hadith.display_title || hadith.id}
        </span>
      </nav>

      {/* Hadith text section */}
      <Card className="mb-6" aria-label={t('hadithDetail.textAria')}>
        <CardContent className="py-6">
          <div className="flex items-center gap-3 mb-4">
            <h2 className="text-xl font-semibold">
              {hadith.display_title || hadith.id}
            </h2>
            {hadith.grade_composite && (
              <span
                className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold ${gradeColor(hadith.grade_normalized)}`}
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
        {/* Isnad chain — reconstructed from the hadith's TRANSMITTED_TO edges */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t('hadithDetail.isnadChain')}</CardTitle>
          </CardHeader>
          <CardContent>
            {chainLoading ? (
              <div className="space-y-2" data-testid="chain-loading">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-8 bg-muted rounded w-full animate-pulse" />
                ))}
              </div>
            ) : chainNarrators.length > 0 ? (
              <ol className="space-y-0" aria-label={t('hadithDetail.isnadChainAria')}>
                {chainNarrators.map((narrator, idx) => (
                  <li key={narrator.id}>
                    <Link
                      to={`/narrators/${encodeURIComponent(narrator.id)}`}
                      className="block rounded-md border p-2 hover:bg-muted/50 transition-colors"
                    >
                      <span className="font-arabic text-base">{narrator.name_ar}</span>
                      {narrator.name_en && (
                        <span className="block text-xs text-muted-foreground">
                          {narrator.name_en}
                          {narrator.generation ? ` · ${narrator.generation}` : ''}
                        </span>
                      )}
                    </Link>
                    {idx < chainNarrators.length - 1 && (
                      <div className="flex justify-center text-muted-foreground text-xs py-0.5" aria-hidden="true">
                        ↓
                      </div>
                    )}
                  </li>
                ))}
              </ol>
            ) : (
              <div className="flex items-center justify-center min-h-[200px] text-muted-foreground text-sm border rounded-md bg-muted/30 p-4">
                <div className="text-center">
                  <p className="mb-2">{t('hadithDetail.noChainTitle')}</p>
                  <p className="text-xs">
                    {t('hadithDetail.noChainBody')}
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Grading and metadata panel */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t('hadithDetail.grading')}</CardTitle>
          </CardHeader>
          <CardContent>
            {/* Grade bar */}
            {hadith.grade_composite && (
              <div className="mb-4">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-semibold">
                    {t('hadithDetail.primaryGrade', { grade: hadith.grade_composite })}
                  </span>
                </div>
                <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${gradeBarColor(hadith.grade_normalized)}`}
                    style={{ width: gradeBarWidth(hadith.grade_normalized) }}
                  />
                </div>
              </div>
            )}

            {/* Metadata */}
            <div className="mt-4">
              <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                {t('hadithDetail.metadata')}
              </h4>
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
                {hadith.collection_name && (
                  <>
                    <dt className="font-medium text-muted-foreground">{t('hadithDetail.mdCollection')}</dt>
                    <dd>{hadith.collection_name}</dd>
                  </>
                )}
                <dt className="font-medium text-muted-foreground">{t('hadithDetail.mdSourceCorpus')}</dt>
                <dd>{hadith.source_corpus}</dd>
                <dt className="font-medium text-muted-foreground">{t('hadithDetail.mdHadithId')}</dt>
                <dd className="font-mono text-xs">{hadith.id}</dd>
                {hadith.has_sunni_parallel && (
                  <>
                    <dt className="font-medium text-muted-foreground">{t('hadithDetail.mdSunniParallel')}</dt>
                    <dd>{t('common.yes')}</dd>
                  </>
                )}
                {hadith.has_shia_parallel && (
                  <>
                    <dt className="font-medium text-muted-foreground">{t('hadithDetail.mdShiaParallel')}</dt>
                    <dd>{t('common.yes')}</dd>
                  </>
                )}
              </dl>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Chain-derived dating (ig#1042) — terminus ante/post quem from the
          isnad chain's narrator death years. */}
      <Card className="mb-6" data-testid="hadith-dating">
        <CardHeader>
          <CardTitle className="text-lg">{t('hadithDetail.dating')}</CardTitle>
        </CardHeader>
        <CardContent>
          {datingLoading ? (
            <div
              className="h-8 bg-muted rounded w-2/3 animate-pulse"
              data-testid="dating-loading"
            />
          ) : dating &&
            dating.confidence !== 'insufficient_data' &&
            dating.terminus_post_quem_ah != null &&
            dating.terminus_ante_quem_ah != null ? (
            <div className="space-y-3">
              <div className="text-2xl font-semibold">
                {t('hadithDetail.datingRange', {
                  post: dating.terminus_post_quem_ah,
                  ante: dating.terminus_ante_quem_ah,
                })}
              </div>
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
                <dt className="font-medium text-muted-foreground">
                  {t('hadithDetail.datingPostQuem')}
                </dt>
                <dd>{t('hadithDetail.datingYearAh', { year: dating.terminus_post_quem_ah })}</dd>
                <dt className="font-medium text-muted-foreground">
                  {t('hadithDetail.datingAnteQuem')}
                </dt>
                <dd>{t('hadithDetail.datingYearAh', { year: dating.terminus_ante_quem_ah })}</dd>
                <dt className="font-medium text-muted-foreground">
                  {t('hadithDetail.datingSpan')}
                </dt>
                <dd>{t('hadithDetail.datingYears', { count: dating.chain_span_ah ?? 0 })}</dd>
                <dt className="font-medium text-muted-foreground">
                  {t('hadithDetail.datingConfidence')}
                </dt>
                <dd>
                  <Badge variant="outline">
                    {t(`hadithDetail.datingConfidence_${dating.confidence}`)}
                  </Badge>
                </dd>
              </dl>
              <p className="text-xs text-muted-foreground">{dating.note}</p>
            </div>
          ) : (
            <div className="flex items-center justify-center min-h-[80px] text-muted-foreground text-sm border rounded-md bg-muted/30 p-4">
              <p className="text-center">
                {dating?.note ?? t('hadithDetail.datingInsufficient')}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Topics */}
      {hadith.topic_tags && hadith.topic_tags.length > 0 && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">{t('hadithDetail.topics')}</CardTitle>
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
                {t('hadithDetail.parallelHadith', { count: parallelsData?.total ?? parallels.length })}
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3" aria-label={t('hadithDetail.parallelAria', { count: parallels.length })}>
              {parallels.map((p) => (
                <Link key={p.id} to={`/hadiths/${p.id}`} className="block">
                  <Card className="hover:shadow-md transition-shadow">
                    <CardContent className="py-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-sm">{p.source_corpus}</span>
                        {p.similarity_score != null && (
                          <span className={`text-xs font-medium ${similarityLevel(p.similarity_score)}`}>
                            {t('hadithDetail.similarityPercent', { percent: (p.similarity_score * 100).toFixed(0) })}
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
                            {t('common.crossSect')}
                          </Badge>
                        )}
                        <Link
                          to={`/compare?a=${id}&b=${p.id}`}
                          className="text-primary hover:underline ms-auto"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {t('nav.compare')}
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
          <CardTitle className="text-lg">{t('hadithDetail.citeShare')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-4">
            <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">
              {t('hadithDetail.academicCitation')}
            </h4>
            <p className="text-sm p-3 rounded-md bg-muted/30 font-mono leading-relaxed">
              {citation}
            </p>
          </div>
          <div className="flex flex-wrap gap-2" aria-live="polite">
            <Button
              variant="outline"
              size="sm"
              onClick={() => copyToClipboard(citation, 'citation')}
            >
              {copiedField === 'citation' ? t('hadithDetail.copied') : t('hadithDetail.copyCitation')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => copyToClipboard(hadith.matn_ar, 'arabic')}
            >
              {copiedField === 'arabic' ? t('hadithDetail.copied') : t('hadithDetail.copyArabic')}
            </Button>
            {hadith.matn_en && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => copyToClipboard(hadith.matn_en!, 'translation')}
              >
                {copiedField === 'translation' ? t('hadithDetail.copied') : t('hadithDetail.copyTranslation')}
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => copyToClipboard(window.location.href, 'link')}
            >
              {copiedField === 'link' ? t('hadithDetail.linkCopied') : t('hadithDetail.copyLink')}
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={handleShare}
            >
              {copiedField === 'share' ? t('hadithDetail.linkCopied') : t('hadithDetail.share')}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
