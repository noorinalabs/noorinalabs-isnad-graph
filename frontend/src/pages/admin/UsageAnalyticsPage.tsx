import { useQuery } from '@tanstack/react-query'
import { fetchUsageAnalytics } from '../../api/admin-client'

export default function UsageAnalyticsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-analytics'],
    queryFn: fetchUsageAnalytics,
  })

  return (
    <div>
      <h2>Usage Analytics</h2>

      {isLoading && <p>Loading...</p>}
      {error && <p style={{ color: 'red' }}>Error: {(error as Error).message}</p>}

      {data && (
        <>
          <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', flexWrap: 'wrap' }}>
            <div
              style={{
                border: '1px solid #ddd',
                borderRadius: '8px',
                padding: '1.5rem',
                minWidth: 180,
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: '0.875rem', color: '#666', marginBottom: '0.5rem' }}>
                Search Volume
              </div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#333' }}>
                {data.search_volume.toLocaleString()}
              </div>
            </div>
            <div
              style={{
                border: '1px solid #ddd',
                borderRadius: '8px',
                padding: '1.5rem',
                minWidth: 180,
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: '0.875rem', color: '#666', marginBottom: '0.5rem' }}>
                API Calls
              </div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#333' }}>
                {data.api_call_count.toLocaleString()}
              </div>
            </div>
          </div>

          <h3>Popular Narrators</h3>
          {data.popular_narrators.length === 0 ? (
            <p style={{ color: '#666' }}>No data available yet.</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', maxWidth: 600 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #ddd', textAlign: 'left' }}>
                  <th style={{ padding: '0.5rem' }}>Narrator</th>
                  <th style={{ padding: '0.5rem' }}>Queries</th>
                </tr>
              </thead>
              <tbody>
                {data.popular_narrators.map((n) => (
                  <tr key={n.id} style={{ borderBottom: '1px solid #eee' }}>
                    <td style={{ padding: '0.5rem' }}>{n.name}</td>
                    <td style={{ padding: '0.5rem' }}>{n.query_count.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  )
}
