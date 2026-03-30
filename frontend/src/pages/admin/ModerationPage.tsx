import { useState } from 'react'
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
      <h2>Content Moderation</h2>

      <div className="flag-box">
        <h3>Flag Content</h3>
        <div className="flex-row" style={{ flexWrap: 'wrap' }}>
          <select
            value={flagForm.entity_type}
            onChange={(e) => setFlagForm({ ...flagForm, entity_type: e.target.value })}
            className="form-input"
            aria-label="Entity type"
          >
            <option value="hadith">Hadith</option>
            <option value="narrator">Narrator</option>
          </select>
          <input
            type="text"
            placeholder="Entity ID"
            aria-label="Entity ID"
            value={flagForm.entity_id}
            onChange={(e) => setFlagForm({ ...flagForm, entity_id: e.target.value })}
            className="form-input"
            style={{ flex: 1, minWidth: 200 }}
          />
          <input
            type="text"
            placeholder="Reason"
            aria-label="Reason for flagging"
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
            Flag
          </button>
        </div>
      </div>

      <div className="flex-row" style={{ marginBottom: '1rem' }}>
        <label>Filter by status:</label>
        <select
          value={statusFilter ?? ''}
          onChange={(e) => {
            setStatusFilter(e.target.value || undefined)
            setPage(1)
          }}
          className="form-input"
        >
          <option value="">All</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      {isLoading && <p>Loading...</p>}
      {error && <p className="error-text">Error: {(error as Error).message}</p>}

      {data && (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Entity ID</th>
                <th>Reason</th>
                <th>Status</th>
                <th>Flagged</th>
                <th>Actions</th>
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
                          Approve
                        </button>
                        <button
                          onClick={() =>
                            updateMutation.mutate({ id: item.id, status: 'rejected' })
                          }
                          disabled={updateMutation.isPending}
                          className="btn-sm"
                        >
                          Reject
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
                Previous
              </button>
              <span>
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
