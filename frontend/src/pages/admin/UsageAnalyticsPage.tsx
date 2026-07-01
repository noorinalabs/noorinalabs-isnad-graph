import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { fetchUsageAnalytics } from '../../api/admin-client'

export default function UsageAnalyticsPage() {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-analytics'],
    queryFn: fetchUsageAnalytics,
  })

  return (
    <div>
      <h2>{t('admin.usageAnalytics.title')}</h2>

      {isLoading && <p>{t('admin.common.loading')}</p>}
      {error && (
        <p className="error-text">{t('common.error', { message: (error as Error).message })}</p>
      )}

      {data && (
        <>
          <div className="flex-row-wrap" style={{ marginBottom: '2rem' }}>
            <div className="stat-card">
              <div className="stat-card-label">{t('admin.usageAnalytics.statSearchVolume')}</div>
              <div className="stat-card-value">{data.search_volume.toLocaleString()}</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">{t('admin.usageAnalytics.statApiCalls')}</div>
              <div className="stat-card-value">{data.api_call_count.toLocaleString()}</div>
            </div>
          </div>

          <h3>{t('admin.usageAnalytics.popularNarrators')}</h3>
          {data.popular_narrators.length === 0 ? (
            <p className="muted-text">{t('admin.usageAnalytics.noData')}</p>
          ) : (
            <table className="data-table" style={{ maxWidth: 600 }}>
              <thead>
                <tr>
                  <th>{t('admin.usageAnalytics.colNarrator')}</th>
                  <th>{t('admin.usageAnalytics.colQueries')}</th>
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
