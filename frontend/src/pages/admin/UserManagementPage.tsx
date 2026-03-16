import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchAdminUsers, updateAdminUser } from '../../api/admin-client'
import type { AdminUser } from '../../types/admin'

export default function UserManagementPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [inputValue, setInputValue] = useState('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-users', page, search],
    queryFn: () => fetchAdminUsers(page, 20, search || undefined),
  })

  const suspendMutation = useMutation({
    mutationFn: (user: AdminUser) =>
      updateAdminUser(user.id, { is_suspended: !user.is_suspended }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-users'] }),
  })

  const promoteMutation = useMutation({
    mutationFn: (user: AdminUser) =>
      updateAdminUser(user.id, { is_admin: !user.is_admin }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-users'] }),
  })

  const handleSearch = () => {
    setSearch(inputValue)
    setPage(1)
  }

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0

  return (
    <div>
      <h2>User Management</h2>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <input
          type="text"
          placeholder="Search users by name or email..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          style={{ padding: '0.5rem', flex: 1, maxWidth: 400 }}
        />
        <button onClick={handleSearch} style={{ padding: '0.5rem 1rem' }}>
          Search
        </button>
      </div>

      {isLoading && <p>Loading...</p>}
      {error && <p style={{ color: 'red' }}>Error: {(error as Error).message}</p>}

      {data && (
        <>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #ddd', textAlign: 'left' }}>
                <th style={{ padding: '0.5rem' }}>Name</th>
                <th style={{ padding: '0.5rem' }}>Email</th>
                <th style={{ padding: '0.5rem' }}>Provider</th>
                <th style={{ padding: '0.5rem' }}>Role</th>
                <th style={{ padding: '0.5rem' }}>Status</th>
                <th style={{ padding: '0.5rem' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((u) => (
                <tr key={u.id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={{ padding: '0.5rem' }}>
                    {u.name}
                    {u.is_admin && (
                      <span
                        style={{
                          marginLeft: '0.5rem',
                          fontSize: '0.75rem',
                          background: '#e8f0fe',
                          color: '#1a73e8',
                          padding: '0.125rem 0.375rem',
                          borderRadius: '4px',
                        }}
                      >
                        Admin
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '0.5rem' }}>{u.email}</td>
                  <td style={{ padding: '0.5rem' }}>{u.provider}</td>
                  <td style={{ padding: '0.5rem' }}>{u.role ?? '-'}</td>
                  <td style={{ padding: '0.5rem' }}>
                    <span
                      style={{
                        color: u.is_suspended ? '#d93025' : '#188038',
                        fontWeight: 600,
                      }}
                    >
                      {u.is_suspended ? 'Suspended' : 'Active'}
                    </span>
                  </td>
                  <td style={{ padding: '0.5rem', display: 'flex', gap: '0.25rem' }}>
                    <button
                      onClick={() => suspendMutation.mutate(u)}
                      disabled={suspendMutation.isPending}
                      style={{
                        padding: '0.25rem 0.5rem',
                        fontSize: '0.8rem',
                        cursor: 'pointer',
                        background: u.is_suspended ? '#e6f4ea' : '#fce8e6',
                        border: '1px solid #ccc',
                        borderRadius: '4px',
                      }}
                    >
                      {u.is_suspended ? 'Unsuspend' : 'Suspend'}
                    </button>
                    <button
                      onClick={() => promoteMutation.mutate(u)}
                      disabled={promoteMutation.isPending}
                      style={{
                        padding: '0.25rem 0.5rem',
                        fontSize: '0.8rem',
                        cursor: 'pointer',
                        background: u.is_admin ? '#fce8e6' : '#e8f0fe',
                        border: '1px solid #ccc',
                        borderRadius: '4px',
                      }}
                    >
                      {u.is_admin ? 'Demote' : 'Promote'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div
            style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}
          >
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span>
              Page {data.page} of {totalPages}
            </span>
            <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Next
            </button>
          </div>
        </>
      )}
    </div>
  )
}
