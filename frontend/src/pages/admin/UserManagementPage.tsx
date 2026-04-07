import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchAdminUsers,
  updateAdminUser,
  updateUserRole,
  bulkUserAction,
  fetchUserDetail,
  getUsersExportUrl,
} from '../../api/admin-client'
import type { AdminUser } from '../../types/admin'

const ROLES = ['viewer', 'editor', 'moderator', 'admin'] as const

export default function UserManagementPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [inputValue, setInputValue] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [bulkRole, setBulkRole] = useState('viewer')
  const [detailUserId, setDetailUserId] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-users', page, search, roleFilter, statusFilter],
    queryFn: () => fetchAdminUsers(page, 20, search || undefined, roleFilter || undefined),
  })

  const { data: userDetail } = useQuery({
    queryKey: ['admin-user-detail', detailUserId],
    queryFn: () => fetchUserDetail(detailUserId!),
    enabled: !!detailUserId,
  })

  const suspendMutation = useMutation({
    mutationFn: (user: AdminUser) =>
      updateAdminUser(user.id, { is_suspended: !user.is_suspended }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-users'] }),
  })

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      updateUserRole(userId, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-users'] }),
  })

  const bulkMutation = useMutation({
    mutationFn: ({ action, role }: { action: string; role?: string }) =>
      bulkUserAction(Array.from(selectedIds), action, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      setSelectedIds(new Set())
    },
  })

  const handleSearch = () => {
    setSearch(inputValue)
    setPage(1)
  }

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (!data) return
    const allIds = data.items.map((u) => u.id)
    const allSelected = allIds.every((id) => selectedIds.has(id))
    if (allSelected) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(allIds))
    }
  }

  const filteredItems = data?.items.filter((u) => {
    if (statusFilter === 'active' && u.is_suspended) return false
    if (statusFilter === 'suspended' && !u.is_suspended) return false
    return true
  })

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <h2>User Management</h2>
        <a
          href={getUsersExportUrl(search || undefined, roleFilter || undefined)}
          className="btn"
          style={{ textDecoration: 'none' }}
          download
        >
          Export CSV
        </a>
      </div>

      <div className="flex-row" style={{ marginBottom: '1rem', gap: '0.5rem', flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="Search users by name or email..."
          aria-label="Search users by name or email"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="form-input"
          style={{ flex: 1, maxWidth: 300 }}
        />
        <button onClick={handleSearch} className="btn">Search</button>
        <select className="form-input" value={roleFilter} onChange={(e) => { setRoleFilter(e.target.value); setPage(1) }} style={{ width: 140 }}>
          <option value="">All Roles</option>
          {ROLES.map((r) => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
        </select>
        <select className="form-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: 140 }}>
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </select>
      </div>

      {selectedIds.size > 0 && (
        <div className="flex-row" style={{ marginBottom: '1rem', gap: '0.5rem', padding: '0.75rem', background: 'var(--color-accent)', borderRadius: 'var(--radius-md)', alignItems: 'center' }}>
          <span style={{ fontSize: 'var(--text-sm)', fontWeight: 500 }}>{selectedIds.size} selected</span>
          <button className="btn-action btn-action-suspend" onClick={() => bulkMutation.mutate({ action: 'suspend' })} disabled={bulkMutation.isPending}>Bulk Suspend</button>
          <button className="btn-action btn-action-unsuspend" onClick={() => bulkMutation.mutate({ action: 'unsuspend' })} disabled={bulkMutation.isPending}>Bulk Unsuspend</button>
          <select className="form-input" value={bulkRole} onChange={(e) => setBulkRole(e.target.value)} style={{ width: 120 }}>
            {ROLES.map((r) => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
          </select>
          <button className="btn-action" onClick={() => bulkMutation.mutate({ action: 'role_change', role: bulkRole })} disabled={bulkMutation.isPending}>Set Role</button>
        </div>
      )}

      {isLoading && <p>Loading...</p>}
      {error && <p className="error-text">Error: {(error as Error).message}</p>}

      {filteredItems && (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input type="checkbox" checked={filteredItems.length > 0 && filteredItems.every((u) => selectedIds.has(u.id))} onChange={toggleSelectAll} aria-label="Select all users" />
                </th>
                <th>Name</th>
                <th>Email</th>
                <th>Provider</th>
                <th>Role</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((u) => (
                <tr key={u.id}>
                  <td><input type="checkbox" checked={selectedIds.has(u.id)} onChange={() => toggleSelect(u.id)} aria-label={`Select ${u.name}`} /></td>
                  <td>
                    <button onClick={() => setDetailUserId(u.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-primary)', textDecoration: 'underline', fontFamily: 'inherit', fontSize: 'inherit', padding: 0 }}>
                      {u.name}
                    </button>
                  </td>
                  <td>{u.email}</td>
                  <td>{u.provider}</td>
                  <td>
                    <select className="form-input" value={u.role ?? 'viewer'} onChange={(e) => roleMutation.mutate({ userId: u.id, role: e.target.value })} disabled={roleMutation.isPending} style={{ width: 120, padding: '0.25rem' }}>
                      {ROLES.map((r) => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
                    </select>
                  </td>
                  <td>
                    <span className={u.is_suspended ? 'text-suspended' : 'text-active'}>{u.is_suspended ? 'Suspended' : 'Active'}</span>
                  </td>
                  <td className="flex-row" style={{ gap: '0.25rem' }}>
                    <button onClick={() => suspendMutation.mutate(u)} disabled={suspendMutation.isPending} className={`btn-action ${u.is_suspended ? 'btn-action-unsuspend' : 'btn-action-suspend'}`}>
                      {u.is_suspended ? 'Unsuspend' : 'Suspend'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="pagination">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
            <span>Page {data!.page} of {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        </>
      )}

      {detailUserId && userDetail && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }} onClick={() => setDetailUserId(null)}>
          <div style={{ background: 'var(--color-card)', borderRadius: 'var(--radius-lg)', padding: 'var(--spacing-6)', minWidth: 400, maxWidth: 600, boxShadow: 'var(--shadow-lg)' }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: 'var(--spacing-4)', fontFamily: 'var(--font-heading)' }}>User Detail</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)' }}>
              <div><div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted-foreground)' }}>Name</div><div style={{ fontWeight: 500 }}>{userDetail.name}</div></div>
              <div><div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted-foreground)' }}>Email</div><div style={{ fontWeight: 500 }}>{userDetail.email}</div></div>
              <div><div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted-foreground)' }}>Provider</div><div style={{ fontWeight: 500 }}>{userDetail.provider}</div></div>
              <div><div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted-foreground)' }}>Role</div><div style={{ fontWeight: 500 }}>{userDetail.role ?? 'viewer'}</div></div>
              <div><div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted-foreground)' }}>Status</div><div style={{ fontWeight: 500 }}>{userDetail.is_suspended ? 'Suspended' : 'Active'}</div></div>
              <div><div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted-foreground)' }}>Member Since</div><div style={{ fontWeight: 500 }}>{new Date(userDetail.created_at).toLocaleDateString()}</div></div>
              <div><div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted-foreground)' }}>Total Logins</div><div style={{ fontWeight: 500 }}>{userDetail.login_count}</div></div>
              <div><div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted-foreground)' }}>Last Login</div><div style={{ fontWeight: 500 }}>{userDetail.last_login ? new Date(userDetail.last_login).toLocaleString() : '-'}</div></div>
            </div>
            <button className="btn" onClick={() => setDetailUserId(null)} style={{ marginTop: 'var(--spacing-4)' }}>Close</button>
          </div>
        </div>
      )}
    </div>
  )
}
