import { useQuery } from '@tanstack/react-query'
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
function scopeSentence(data: ContentStats): string {
  const collections = `${data.collection_count.toLocaleString()} collection${
    data.collection_count === 1 ? '' : 's'
  }`
  const sectNames = data.sects.map((s) => titleCase(s.sect))
  if (sectNames.length === 0) {
    return `${data.hadith_count.toLocaleString()} hadith across ${collections}.`
  }
  const sects =
    sectNames.length === 1
      ? `${sectNames[0]} only`
      : sectNames.join(', ')
  return `${data.hadith_count.toLocaleString()} hadith across ${collections} — ${sects}.`
}

export default function ContentStatsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: fetchContentStats,
  })

  return (
    <div>
      <h2>Content Statistics</h2>

      {isLoading && <p>Loading...</p>}
      {error && <p className={styles.errorText}>Error: {(error as Error).message}</p>}

      {data && (
        <>
          <div className={styles.cardGrid}>
            <StatCard label="Hadiths" value={data.hadith_count.toLocaleString()} />
            <StatCard
              label="Narrators"
              value={data.narrator_count.toLocaleString()}
              hint="raw nodes — segmentation in progress"
            />
            <StatCard label="Collections" value={data.collection_count.toLocaleString()} />
            <StatCard
              label="Linked to a collection"
              value={`${data.coverage_pct}%`}
            />
          </div>

          <p className={styles.scopeCaption}>{scopeSentence(data)}</p>
          <p className={styles.scopeNote}>
            These figures reflect the data currently loaded, not a complete hadith corpus.
            The narrator count is the raw <code>Narrator</code> node total and still
            includes unsegmented isnad chains; a de-duplicated figure will follow once
            segmentation completes.
          </p>

          {data.sects.length > 0 && (
            <section className={styles.breakdown}>
              <h3 className={styles.sectionTitle}>By sect</h3>
              <table className="data-table" style={{ maxWidth: 480 }}>
                <thead>
                  <tr>
                    <th>Sect</th>
                    <th>Collections</th>
                    <th>Hadith count</th>
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
              <h3 className={styles.sectionTitle}>By collection</h3>
              <table className="data-table" style={{ maxWidth: 480 }}>
                <thead>
                  <tr>
                    <th>Collection</th>
                    <th>Sect</th>
                    <th>Hadith count</th>
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
