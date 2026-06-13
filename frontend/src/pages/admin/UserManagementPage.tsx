import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchAdminUsers,
  fetchAdminUser,
  fetchRoles,
  setUserRole,
} from '../../api/admin-client'
import { deriveHighestRole, type UserRole } from '../../hooks/useAuth'

// The selectable role vocabulary mirrors the user-service canonical hierarchy
// (ontology/repos/user-service.yaml → trial | reader | researcher | admin).
// The live options shown come from the role *catalog* (fetchRoles) so the panel
// reflects whatever roles the user-service actually defines; this constant is
// only the fallback ordering for the highest-role display.
const ROLE_ORDER: UserRole[] = ['trial', 'reader', 'researcher', 'admin']

function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export default function UserManagementPage() {
  const queryClient = useQueryClient()
  // user-service list pagination is cursor-based (opaque `next_cursor`), not
  // page-numbered. Keep a stack of the cursors we've visited so "Previous" can
  // pop back; the first entry is `null` (the initial, un-cursored page).
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null])
  const cursor = cursorStack[cursorStack.length - 1]
  const [detailUserId, setDetailUserId] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-users', cursor],
    queryFn: () => fetchAdminUsers(cursor, 20),
  })

  const { data: roles } = useQuery({
    queryKey: ['admin-roles'],
    queryFn: fetchRoles,
  })

  const { data: userDetail } = useQuery({
    queryKey: ['admin-user-detail', detailUserId],
    queryFn: () => fetchAdminUser(detailUserId!),
    enabled: !!detailUserId,
  })

  const roleMutation = useMutation({
    mutationFn: ({
      userId,
      role,
      currentRoles,
    }: {
      userId: string
      role: string
      currentRoles: string[]
    }) => setUserRole(userId, role, currentRoles, roles ?? []),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-users'] }),
  })

  const goNext = () => {
    if (data?.next_cursor) {
      setCursorStack((s) => [...s, data.next_cursor!])
    }
  }

  const goPrev = () => {
    setCursorStack((s) => (s.length > 1 ? s.slice(0, -1) : s))
  }

  // Role names available for assignment. Prefer the live catalog; fall back to
  // the canonical ordering before the catalog query resolves.
  const roleOptions: string[] = roles?.length
    ? roles.map((r) => r.name)
    : ROLE_ORDER

  return (
    <div>
      <div className="mb-4">
        <h2>User Management</h2>
        <p className="small-muted">
          Users and roles are managed by the user-service. Admin access requires
          the <code>admin</code> role on your user-service account.
        </p>
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
                <th>Verified</th>
                <th>Role</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((u) => {
                const currentRoles = u.roles ?? []
                return (
                  <tr key={u.id}>
                    <td>
                      <button
                        onClick={() => setDetailUserId(u.id)}
                        className="cursor-pointer border-none p-0 text-primary underline"
                        style={{
                          background: 'none',
                          fontFamily: 'inherit',
                          fontSize: 'inherit',
                        }}
                      >
                        {u.display_name ?? u.email}
                      </button>
                    </td>
                    <td>{u.email}</td>
                    <td>
                      <span className={u.email_verified ? 'text-active' : 'text-suspended'}>
                        {u.email_verified ? 'Verified' : 'Unverified'}
                      </span>
                    </td>
                    <td>
                      <select
                        className="form-input w-[130px] p-1"
                        value={deriveHighestRole(currentRoles)}
                        onChange={(e) =>
                          roleMutation.mutate({
                            userId: u.id,
                            role: e.target.value,
                            currentRoles,
                          })
                        }
                        disabled={roleMutation.isPending || !roles}
                        aria-label={`Role for ${u.display_name ?? u.email}`}
                      >
                        {roleOptions.map((r) => (
                          <option key={r} value={r}>
                            {titleCase(r)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <span className={u.is_active ? 'text-active' : 'text-suspended'}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          {data.items.length === 0 && <p>No users found.</p>}

          <div className="pagination">
            <button disabled={cursorStack.length <= 1} onClick={goPrev}>
              Previous
            </button>
            <button disabled={!data.next_cursor} onClick={goNext}>
              Next
            </button>
          </div>
        </>
      )}

      {detailUserId && userDetail && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.5)' }}
          onClick={() => setDetailUserId(null)}
        >
          <div
            className="rounded-lg bg-card p-6 min-w-[400px] max-w-[600px]"
            style={{
              boxShadow: 'var(--shadow-lg)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-4" style={{ fontFamily: 'var(--font-heading)' }}>
              User Detail
            </h3>
            <div className="grid gap-3" style={{ gridTemplateColumns: '1fr 1fr' }}>
              <DetailField label="Name" value={userDetail.display_name ?? '—'} />
              <DetailField label="Email" value={userDetail.email} />
              <DetailField
                label="Email Verified"
                value={userDetail.email_verified ? 'Yes' : 'No'}
              />
              <DetailField label="Status" value={userDetail.is_active ? 'Active' : 'Inactive'} />
              <DetailField label="Locale" value={userDetail.locale ?? '—'} />
              <DetailField
                label="Roles"
                value={userDetail.roles?.length ? userDetail.roles.join(', ') : '—'}
              />
              <DetailField
                label="Member Since"
                value={new Date(userDetail.created_at).toLocaleDateString()}
              />
            </div>
            <button
              className="btn mt-4"
              onClick={() => setDetailUserId(null)}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function DetailField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-muted-foreground" style={{ fontSize: 'var(--text-xs)' }}>
        {label}
      </div>
      <div className="font-medium">{value}</div>
    </div>
  )
}
