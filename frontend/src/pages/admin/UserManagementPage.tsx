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

      <div className="flex-row" style={{ marginBottom: '1rem' }}>
        <input
          type="text"
          placeholder="Search users by name or email..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="form-input"
          style={{ flex: 1, maxWidth: 400 }}
        />
        <button onClick={handleSearch} className="btn">
          Search
        </button>
      </div>

      {isLoading && <p>Loading...</p>}
      {error && <p className="error-text">Error: {(error as Error).message}</p>}

      {data && (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Provider</th>
                <th>Role</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((u) => (
                <tr key={u.id}>
                  <td>
                    {u.name}
                    {u.is_admin && <span className="badge-admin">Admin</span>}
                  </td>
                  <td>{u.email}</td>
                  <td>{u.provider}</td>
                  <td>{u.role ?? '-'}</td>
                  <td>
                    <span className={u.is_suspended ? 'text-suspended' : 'text-active'}>
                      {u.is_suspended ? 'Suspended' : 'Active'}
                    </span>
                  </td>
                  <td className="flex-row" style={{ gap: '0.25rem' }}>
                    <button
                      onClick={() => suspendMutation.mutate(u)}
                      disabled={suspendMutation.isPending}
                      className={`btn-action ${u.is_suspended ? 'btn-action-unsuspend' : 'btn-action-suspend'}`}
                    >
                      {u.is_suspended ? 'Unsuspend' : 'Suspend'}
                    </button>
                    <button
                      onClick={() => promoteMutation.mutate(u)}
                      disabled={promoteMutation.isPending}
                      className={`btn-action ${u.is_admin ? 'btn-action-demote' : 'btn-action-promote'}`}
                    >
                      {u.is_admin ? 'Demote' : 'Promote'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="pagination">
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
