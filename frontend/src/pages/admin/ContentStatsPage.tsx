import { useQuery } from '@tanstack/react-query'
import { fetchContentStats } from '../../api/admin-client'
import styles from './ContentStatsPage.module.css'

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className={styles.card}>
      <div className={styles.cardLabel}>{label}</div>
      <div className={styles.cardValue}>{value}</div>
    </div>
  )
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
        <div className={styles.cardGrid}>
          <StatCard label="Hadiths" value={data.hadith_count.toLocaleString()} />
          <StatCard label="Narrators" value={data.narrator_count.toLocaleString()} />
          <StatCard label="Collections" value={data.collection_count.toLocaleString()} />
          <StatCard label="Coverage" value={`${data.coverage_pct}%`} />
        </div>
      )}
    </div>
  )
}
