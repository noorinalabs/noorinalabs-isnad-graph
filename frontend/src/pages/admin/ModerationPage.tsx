import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchModerationItems,
  updateModerationItem,
  flagContent,
} from '../../api/client'
import type { ModerationItem } from '../../types/api'

function statusBadgeClass(status: string): string {
  if (status === 'approved') return 'badge-approved'
  if (status === 'rejected') return 'badge-rejected'
  return 'badge-pending'
}

export default function ModerationPage() {
  const { t } = useTranslation()
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: ['moderation', page, statusFilter],
    queryFn: () => fetchModerationItems(page, 20, statusFilter),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, status, notes }: { id: string; status: string; notes?: string }) =>
      updateModerationItem(id, status, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['moderation'] })
    },
  })

  const flagMutation = useMutation({
    mutationFn: (body: { entity_type: string; entity_id: string; reason: string }) =>
      flagContent(body.entity_type, body.entity_id, body.reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['moderation'] })
    },
  })

  const [flagForm, setFlagForm] = useState({ entity_type: 'hadith', entity_id: '', reason: '' })

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0

  return (
    <div>
      <h2>{t('admin.moderation.title')}</h2>

      <div className="flag-box">
        <h3>{t('admin.moderation.flagContent')}</h3>
        <div className="flex-row" style={{ flexWrap: 'wrap' }}>
          <select
            value={flagForm.entity_type}
            onChange={(e) => setFlagForm({ ...flagForm, entity_type: e.target.value })}
            className="form-input"
            aria-label={t('admin.moderation.entityTypeLabel')}
          >
            <option value="hadith">{t('admin.moderation.entityHadith')}</option>
            <option value="narrator">{t('admin.moderation.entityNarrator')}</option>
          </select>
          <input
            type="text"
            placeholder={t('admin.moderation.entityIdPlaceholder')}
            aria-label={t('admin.moderation.entityIdLabel')}
            value={flagForm.entity_id}
            onChange={(e) => setFlagForm({ ...flagForm, entity_id: e.target.value })}
            className="form-input"
            style={{ flex: 1, minWidth: 200 }}
          />
          <input
            type="text"
            placeholder={t('admin.moderation.reasonPlaceholder')}
            aria-label={t('admin.moderation.reasonLabel')}
            value={flagForm.reason}
            onChange={(e) => setFlagForm({ ...flagForm, reason: e.target.value })}
            className="form-input"
            style={{ flex: 2, minWidth: 200 }}
          />
          <button
            onClick={() => {
              if (flagForm.entity_id && flagForm.reason) {
                flagMutation.mutate(flagForm)
                setFlagForm({ ...flagForm, entity_id: '', reason: '' })
              }
            }}
            disabled={flagMutation.isPending}
            className="btn"
          >
            {t('admin.moderation.flag')}
          </button>
        </div>
      </div>

      <div className="flex-row" style={{ marginBottom: '1rem' }}>
        <label>{t('admin.moderation.filterByStatus')}</label>
        <select
          value={statusFilter ?? ''}
          onChange={(e) => {
            setStatusFilter(e.target.value || undefined)
            setPage(1)
          }}
          className="form-input"
        >
          <option value="">{t('admin.moderation.statusAll')}</option>
          <option value="pending">{t('admin.moderation.statusPending')}</option>
          <option value="approved">{t('admin.moderation.statusApproved')}</option>
          <option value="rejected">{t('admin.moderation.statusRejected')}</option>
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
                <th>{t('admin.moderation.colType')}</th>
                <th>{t('admin.moderation.colEntityId')}</th>
                <th>{t('admin.moderation.colReason')}</th>
                <th>{t('admin.moderation.colStatus')}</th>
                <th>{t('admin.moderation.colFlagged')}</th>
                <th>{t('admin.moderation.colActions')}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item: ModerationItem) => (
                <tr key={item.id}>
                  <td>{item.entity_type}</td>
                  <td className="mono">{item.entity_id}</td>
                  <td>{item.reason}</td>
                  <td>
                    <span className={statusBadgeClass(item.status)}>
                      {item.status}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.85rem' }}>
                    {new Date(item.flagged_at).toLocaleDateString()}
                  </td>
                  <td>
                    {item.status === 'pending' && (
                      <div className="flex-row" style={{ gap: '0.25rem' }}>
                        <button
                          onClick={() =>
                            updateMutation.mutate({ id: item.id, status: 'approved' })
                          }
                          disabled={updateMutation.isPending}
                          className="btn-sm"
                        >
                          {t('admin.moderation.approve')}
                        </button>
                        <button
                          onClick={() =>
                            updateMutation.mutate({ id: item.id, status: 'rejected' })
                          }
                          disabled={updateMutation.isPending}
                          className="btn-sm"
                        >
                          {t('admin.moderation.reject')}
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="pagination">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>
                {t('common.previous')}
              </button>
              <span>{t('common.pageOf', { current: page, total: totalPages })}</span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >
                {t('common.next')}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
