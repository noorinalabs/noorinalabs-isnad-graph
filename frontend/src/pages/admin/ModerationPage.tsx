import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchModerationItems,
  updateModerationItem,
  flagContent,
} from '../../api/client'
import type { ModerationItem } from '../../types/api'

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

      <div style={{ marginBottom: '1.5rem', padding: '1rem', border: '1px solid #ddd' }}>
        <h3 style={{ marginTop: 0 }}>Flag Content</h3>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <select
            value={flagForm.entity_type}
            onChange={(e) => setFlagForm({ ...flagForm, entity_type: e.target.value })}
            style={{ padding: '0.5rem' }}
          >
            <option value="hadith">Hadith</option>
            <option value="narrator">Narrator</option>
          </select>
          <input
            type="text"
            placeholder="Entity ID"
            value={flagForm.entity_id}
            onChange={(e) => setFlagForm({ ...flagForm, entity_id: e.target.value })}
            style={{ padding: '0.5rem', flex: 1, minWidth: 200 }}
          />
          <input
            type="text"
            placeholder="Reason"
            value={flagForm.reason}
            onChange={(e) => setFlagForm({ ...flagForm, reason: e.target.value })}
            style={{ padding: '0.5rem', flex: 2, minWidth: 200 }}
          />
          <button
            onClick={() => {
              if (flagForm.entity_id && flagForm.reason) {
                flagMutation.mutate(flagForm)
                setFlagForm({ ...flagForm, entity_id: '', reason: '' })
              }
            }}
            disabled={flagMutation.isPending}
            style={{ padding: '0.5rem 1rem' }}
          >
            Flag
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <label>Filter by status:</label>
        <select
          value={statusFilter ?? ''}
          onChange={(e) => {
            setStatusFilter(e.target.value || undefined)
            setPage(1)
          }}
          style={{ padding: '0.5rem' }}
        >
          <option value="">All</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      {isLoading && <p>Loading...</p>}
      {error && <p style={{ color: 'red' }}>Error: {(error as Error).message}</p>}

      {data && (
        <>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #ddd', textAlign: 'left' }}>
                <th style={{ padding: '0.5rem' }}>Type</th>
                <th style={{ padding: '0.5rem' }}>Entity ID</th>
                <th style={{ padding: '0.5rem' }}>Reason</th>
                <th style={{ padding: '0.5rem' }}>Status</th>
                <th style={{ padding: '0.5rem' }}>Flagged</th>
                <th style={{ padding: '0.5rem' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item: ModerationItem) => (
                <tr key={item.id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={{ padding: '0.5rem' }}>{item.entity_type}</td>
                  <td style={{ padding: '0.5rem', fontFamily: 'monospace', fontSize: '0.85rem' }}>
                    {item.entity_id}
                  </td>
                  <td style={{ padding: '0.5rem' }}>{item.reason}</td>
                  <td style={{ padding: '0.5rem' }}>
                    <span
                      style={{
                        padding: '0.2rem 0.5rem',
                        borderRadius: '4px',
                        background:
                          item.status === 'approved'
                            ? '#d4edda'
                            : item.status === 'rejected'
                              ? '#f8d7da'
                              : '#fff3cd',
                        color:
                          item.status === 'approved'
                            ? '#155724'
                            : item.status === 'rejected'
                              ? '#721c24'
                              : '#856404',
                      }}
                    >
                      {item.status}
                    </span>
                  </td>
                  <td style={{ padding: '0.5rem', fontSize: '0.85rem' }}>
                    {new Date(item.flagged_at).toLocaleDateString()}
                  </td>
                  <td style={{ padding: '0.5rem' }}>
                    {item.status === 'pending' && (
                      <div style={{ display: 'flex', gap: '0.25rem' }}>
                        <button
                          onClick={() =>
                            updateMutation.mutate({ id: item.id, status: 'approved' })
                          }
                          disabled={updateMutation.isPending}
                          style={{ padding: '0.25rem 0.5rem', fontSize: '0.85rem' }}
                        >
                          Approve
                        </button>
                        <button
                          onClick={() =>
                            updateMutation.mutate({ id: item.id, status: 'rejected' })
                          }
                          disabled={updateMutation.isPending}
                          style={{ padding: '0.25rem 0.5rem', fontSize: '0.85rem' }}
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
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
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
