import { useQuery } from '@tanstack/react-query'
import { fetchContentStats } from '../../api/admin-client'

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div
      style={{
        border: '1px solid #ddd',
        borderRadius: '8px',
        padding: '1.5rem',
        minWidth: 180,
        textAlign: 'center',
      }}
    >
      <div style={{ fontSize: '0.875rem', color: '#666', marginBottom: '0.5rem' }}>{label}</div>
      <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#333' }}>{value}</div>
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
      {error && <p style={{ color: 'red' }}>Error: {(error as Error).message}</p>}

      {data && (
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <StatCard label="Hadiths" value={data.hadith_count.toLocaleString()} />
          <StatCard label="Narrators" value={data.narrator_count.toLocaleString()} />
          <StatCard label="Collections" value={data.collection_count.toLocaleString()} />
          <StatCard label="Coverage" value={`${data.coverage_pct}%`} />
        </div>
      )}
    </div>
  )
}
