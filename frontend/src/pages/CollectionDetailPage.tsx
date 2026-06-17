import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { fetchCollection } from '../api/client'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'

export default function CollectionDetailPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()

  const {
    data: collection,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['collection', id],
    queryFn: () => fetchCollection(id!),
    enabled: !!id,
  })

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto space-y-4">
        <div className="h-6 bg-muted rounded w-48 animate-pulse" />
        <Card className="animate-pulse">
          <CardContent className="py-8">
            <div className="h-8 bg-muted rounded w-1/3 mb-4" />
            <div className="h-6 bg-muted rounded w-1/4 mb-6" />
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
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
      <div className="max-w-4xl mx-auto">
        <p className="text-destructive">{t('common.error', { message: (error as Error).message })}</p>
      </div>
    )
  }

  if (!collection) {
    return (
      <div className="max-w-4xl mx-auto">
        <p>{t('collectionDetail.notFound')}</p>
      </div>
    )
  }

  const isSunni = collection.sect.toLowerCase() === 'sunni'

  const metadataFields: [string, string | null][] = [
    [t('collectionDetail.fieldCompiler'), collection.compiler_name],
    [t('collectionDetail.fieldCompilationYear'), collection.compilation_year_ah != null ? `${collection.compilation_year_ah} AH` : null],
    [t('collectionDetail.fieldTotalHadiths'), collection.total_hadiths != null ? collection.total_hadiths.toLocaleString() : null],
    [t('collectionDetail.fieldBooks'), collection.book_count != null ? String(collection.book_count) : null],
    [t('collectionDetail.fieldSect'), collection.sect],
    [t('collectionDetail.fieldCanonicalRank'), collection.canonical_rank != null ? `#${collection.canonical_rank}` : null],
  ]

  return (
    <div className="max-w-4xl mx-auto">
      {/* Breadcrumb */}
      <nav className="mb-4 text-sm text-muted-foreground">
        <Link to="/collections" className="hover:text-foreground">
          {t('nav.collections')}
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-foreground">{collection.name_en}</span>
      </nav>

      {/* Collection profile */}
      <Card className="mb-6">
        <CardContent className="py-6">
          {/* Arabic name first */}
          <div dir="rtl" lang="ar" className="text-[28px] font-arabic leading-relaxed mb-1">
            {collection.name_ar}
          </div>

          {/* English name with sect badge */}
          <div className="flex items-center gap-3 mb-4">
            <h2 className="text-xl font-semibold">{collection.name_en}</h2>
            <Badge variant={isSunni ? 'sunni' : 'shia'}>{collection.sect}</Badge>
          </div>

          {/* Metadata */}
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
            {metadataFields.map(([label, value]) => (
              <div key={label} className="contents">
                <dt className="font-semibold text-muted-foreground">{label}</dt>
                <dd>{value ?? <span className="text-muted-foreground">&mdash;</span>}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      {/* Statistics summary */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">{t('collectionDetail.statisticsTitle')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {[
              [t('collectionDetail.statTotalHadiths'), collection.total_hadiths?.toLocaleString() ?? '--'],
              [t('collectionDetail.statBooks'), collection.book_count != null ? String(collection.book_count) : '--'],
              [t('collectionDetail.statCanonicalRank'), collection.canonical_rank != null ? `#${collection.canonical_rank}` : '--'],
            ].map(([label, value]) => (
              <div key={label} className="p-3 border rounded-md text-center">
                <div className="text-xs text-muted-foreground mb-1">{label}</div>
                <div className="text-lg font-semibold">{value}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Browse link */}
      <div className="flex gap-3">
        <Link to={`/search?q=${encodeURIComponent(collection.name_en)}`}>
          <Button variant="outline">{t('collectionDetail.searchInCollection')}</Button>
        </Link>
      </div>
    </div>
  )
}
