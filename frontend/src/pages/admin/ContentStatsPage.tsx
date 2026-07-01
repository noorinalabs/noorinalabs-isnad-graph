import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { fetchContentStats } from '../../api/admin-client'
import type { ContentStats } from '../../types/admin'
import styles from './ContentStatsPage.module.css'

function StatCard({
  label,
  value,
  hint,
}: {
  label: string
  value: string | number
  hint?: string
}) {
  return (
    <div className={styles.card}>
      <div className={styles.cardLabel}>{label}</div>
      <div className={styles.cardValue}>{value}</div>
      {hint && <div className={styles.cardHint}>{hint}</div>}
    </div>
  )
}

function titleCase(s: string): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s
}

// A plain-language description of corpus *scope* so the totals are not read as
// a complete corpus. Built from the per-sect breakdown the API returns.
function scopeSentence(data: ContentStats, t: TFunction): string {
  const collections = t('admin.contentStats.scopeCollections', { count: data.collection_count })
  const hadiths = data.hadith_count.toLocaleString()
  const sectNames = data.sects.map((s) => titleCase(s.sect))
  if (sectNames.length === 0) {
    return t('admin.contentStats.scopeNoSects', { hadiths, collections })
  }
  const sects =
    sectNames.length === 1
      ? t('admin.contentStats.scopeSectsSingle', { name: sectNames[0] })
      : sectNames.join(', ')
  return t('admin.contentStats.scopeWithSects', { hadiths, collections, sects })
}

export default function ContentStatsPage() {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: fetchContentStats,
  })

  return (
    <div>
      <h2>{t('admin.contentStats.title')}</h2>

      {isLoading && <p>{t('admin.common.loading')}</p>}
      {error && (
        <p className={styles.errorText}>
          {t('common.error', { message: (error as Error).message })}
        </p>
      )}

      {data && (
        <>
          <div className={styles.cardGrid}>
            <StatCard label={t('admin.contentStats.statHadiths')} value={data.hadith_count.toLocaleString()} />
            <StatCard
              label={t('admin.contentStats.statNarrators')}
              value={data.narrator_count.toLocaleString()}
              hint={t('admin.contentStats.statNarratorsHint')}
            />
            <StatCard label={t('admin.contentStats.statCollections')} value={data.collection_count.toLocaleString()} />
            <StatCard
              label={t('admin.contentStats.statLinked')}
              value={`${data.coverage_pct}%`}
            />
          </div>

          <p className={styles.scopeCaption}>{scopeSentence(data, t)}</p>
          <p className={styles.scopeNote}>
            {t('admin.contentStats.scopeNotePre')}
            <code>Narrator</code>
            {t('admin.contentStats.scopeNotePost')}
          </p>

          {data.sects.length > 0 && (
            <section className={styles.breakdown}>
              <h3 className={styles.sectionTitle}>{t('admin.contentStats.sectionBySect')}</h3>
              <table className="data-table" style={{ maxWidth: 480 }}>
                <thead>
                  <tr>
                    <th>{t('admin.contentStats.colSect')}</th>
                    <th>{t('admin.contentStats.colCollections')}</th>
                    <th>{t('admin.contentStats.colHadithCount')}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.sects.map((s) => (
                    <tr key={s.sect}>
                      <td style={{ textTransform: 'capitalize' }}>{s.sect}</td>
                      <td>{s.collection_count.toLocaleString()}</td>
                      <td>{s.hadith_count.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {data.collections.length > 0 && (
            <section className={styles.breakdown}>
              <h3 className={styles.sectionTitle}>{t('admin.contentStats.sectionByCollection')}</h3>
              <table className="data-table" style={{ maxWidth: 480 }}>
                <thead>
                  <tr>
                    <th>{t('admin.contentStats.colCollection')}</th>
                    <th>{t('admin.contentStats.colSect')}</th>
                    <th>{t('admin.contentStats.colHadithCount')}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.collections.map((c) => (
                    <tr key={c.id}>
                      <td>{c.name}</td>
                      <td style={{ textTransform: 'capitalize' }}>{c.sect}</td>
                      <td>{c.hadith_count.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </>
      )}
    </div>
  )
}
