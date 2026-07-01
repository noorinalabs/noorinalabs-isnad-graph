import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { fetchAuditLogs } from '../../api/admin-client'

export default function AuditLogPage() {
  const { t } = useTranslation()
  const [page, setPage] = useState(1)
  const [actionFilter, setActionFilter] = useState('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-audit', page, actionFilter],
    queryFn: () => fetchAuditLogs(page, 20, actionFilter || undefined),
  })

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0

  return (
    <div>
      <h2>{t('admin.auditLog.title')}</h2>

      <div className="flex-row" style={{ marginBottom: '1rem', gap: '0.5rem' }}>
        <select
          className="form-input"
          value={actionFilter}
          onChange={(e) => {
            setActionFilter(e.target.value)
            setPage(1)
          }}
          style={{ width: 200 }}
        >
          <option value="">{t('admin.auditLog.filterAllActions')}</option>
          <option value="role_change">{t('admin.auditLog.actionRoleChange')}</option>
          <option value="bulk_suspend">{t('admin.auditLog.actionBulkSuspend')}</option>
          <option value="bulk_unsuspend">{t('admin.auditLog.actionBulkUnsuspend')}</option>
          <option value="bulk_role_change">{t('admin.auditLog.actionBulkRoleChange')}</option>
        </select>
      </div>

      {isLoading && <p>{t('admin.common.loading')}</p>}
      {error && (
        <p className="error-text">{t('common.error', { message: (error as Error).message })}</p>
      )}

      {data && (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>{t('admin.auditLog.colTime')}</th>
                <th>{t('admin.auditLog.colAction')}</th>
                <th>{t('admin.auditLog.colActor')}</th>
                <th>{t('admin.auditLog.colTarget')}</th>
                <th>{t('admin.auditLog.colDetails')}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((entry) => (
                <tr key={entry.id}>
                  <td>{new Date(entry.created_at).toLocaleString()}</td>
                  <td>
                    <span
                      style={{
                        padding: '0.125rem 0.5rem',
                        borderRadius: 'var(--radius-full)',
                        background: 'var(--color-accent)',
                        fontSize: 'var(--text-xs)',
                        fontWeight: 500,
                      }}
                    >
                      {entry.action}
                    </span>
                  </td>
                  <td>{entry.actor_name || entry.actor_id}</td>
                  <td>{entry.target_user_id ?? '-'}</td>
                  <td>{entry.details}</td>
                </tr>
              ))}
              {data.items.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', color: 'var(--color-muted-foreground)' }}>
                    {t('admin.auditLog.empty')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          <div className="pagination">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              {t('common.previous')}
            </button>
            <span>{t('common.pageOf', { current: data.page, total: totalPages || 1 })}</span>
            <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              {t('common.next')}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
