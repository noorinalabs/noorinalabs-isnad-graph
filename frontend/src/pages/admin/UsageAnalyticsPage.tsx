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
      {error && <p className="error-text">Error: {(error as Error).message}</p>}

      {data && (
        <>
          <div className="flex-row-wrap" style={{ marginBottom: '2rem' }}>
            <div className="stat-card">
              <div className="stat-card-label">Search Volume</div>
              <div className="stat-card-value">{data.search_volume.toLocaleString()}</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">API Calls</div>
              <div className="stat-card-value">{data.api_call_count.toLocaleString()}</div>
            </div>
          </div>

          <h3>Popular Narrators</h3>
          {data.popular_narrators.length === 0 ? (
            <p className="muted-text">No data available yet.</p>
          ) : (
            <table className="data-table" style={{ maxWidth: 600 }}>
              <thead>
                <tr>
                  <th>Narrator</th>
                  <th>Queries</th>
                </tr>
              </thead>
              <tbody>
                {data.popular_narrators.map((n) => (
                  <tr key={n.id}>
                    <td>{n.name}</td>
                    <td>{n.query_count.toLocaleString()}</td>
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
