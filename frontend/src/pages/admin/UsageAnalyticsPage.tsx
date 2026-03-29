import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchUsageAnalytics } from '../../api/admin-client'

const TIME_RANGES = [
  { value: '1h', label: 'Last 1 hour' },
  { value: '24h', label: 'Last 24 hours' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
] as const

type TimeRange = (typeof TIME_RANGES)[number]['value']

export default function UsageAnalyticsPage() {
  const [timeRange, setTimeRange] = useState<TimeRange>('24h')

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-analytics', timeRange],
    queryFn: () => fetchUsageAnalytics(timeRange),
  })

  return (
    <div>
      <div className="flex-row" style={{ alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0 }}>Usage Analytics</h2>
        <select
          value={timeRange}
          onChange={(e) => setTimeRange(e.target.value as TimeRange)}
          className="form-input"
          style={{ marginLeft: 'auto', width: 'auto' }}
        >
          {TIME_RANGES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </div>

      {isLoading && <p>Loading analytics...</p>}
      {error && <p className="error-text">Failed to load analytics: {(error as Error).message}</p>}

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
            <p className="muted-text">No data available for this time range.</p>
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
