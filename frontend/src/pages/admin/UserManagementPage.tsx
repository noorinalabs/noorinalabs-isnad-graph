import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchAdminUsers,
  fetchAdminUser,
  fetchRoles,
  setUserRole,
} from '../../api/admin-client'
import { deriveHighestRole, useAuth, type UserRole } from '../../hooks/useAuth'

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
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { user: currentUser } = useAuth()
  // Per-row error surface for role-change failures (silent before ig#988): a
  // self-demote block or a rejected assign/remove mutation. Keyed by the user
  // id so the message renders under the right row's select, and only one shows
  // at a time (a fresh attempt clears the previous).
  const [roleError, setRoleError] = useState<{ userId: string; message: string } | null>(null)
  // user-service list pagination is cursor-based (opaque `next_cursor`), not
  // page-numbered. Keep a stack of the cursors we've visited so "Previous" can
  // pop back; the first entry is `null` (the initial, un-cursored page).
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null])
  const cursor = cursorStack[cursorStack.length - 1]
  const [detailUserId, setDetailUserId] = useState<string | null>(null)

  // Message shown when an admin tries to strip `admin` from their OWN row. The
  // user-service has no last-admin guard and the isnad-graph backend role route
  // is a 501 stub, so this client-side block is the only thing standing between
  // an operator and a self-inflicted lockout (recovery is the us#159 seed-admin
  // redeploy path). We block rather than confirm() so the demote can never go
  // through by reflex (ig#988).
  const selfDemoteMessage = t('admin.userManagement.selfDemoteMessage')

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
    onSuccess: (_data, variables) => {
      // The assign/remove landed — clear any stale error for this row.
      setRoleError((prev) => (prev?.userId === variables.userId ? null : prev))
      return queryClient.invalidateQueries({ queryKey: ['admin-users'] })
    },
    onError: (err, variables) => {
      // Surface the rejected mutation inline instead of failing silently.
      setRoleError({ userId: variables.userId, message: (err as Error).message })
    },
  })

  // Guarded role change. Blocks an admin from stripping `admin` off their OWN
  // account (self-demote lockout), otherwise runs the assign/remove mutation.
  // A self-demote is "I am editing my own row, I currently hold admin, and the
  // role I'm switching to is not admin" — selecting any lower role removes
  // admin because setUserRole() collapses to exactly the chosen role.
  const handleRoleChange = (userId: string, role: string, currentRoles: string[]) => {
    const isSelf = !!currentUser && currentUser.id === userId
    if (isSelf && currentRoles.includes('admin') && role !== 'admin') {
      setRoleError({ userId, message: selfDemoteMessage })
      return
    }
    setRoleError((prev) => (prev?.userId === userId ? null : prev))
    roleMutation.mutate({ userId, role, currentRoles })
  }

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
        <h2>{t('admin.userManagement.title')}</h2>
        <p className="small-muted">
          {t('admin.userManagement.subtitlePre')}
          <code>admin</code>
          {t('admin.userManagement.subtitlePost')}
        </p>
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
                <th>{t('admin.userManagement.colName')}</th>
                <th>{t('admin.userManagement.colEmail')}</th>
                <th>{t('admin.userManagement.colVerified')}</th>
                <th>{t('admin.userManagement.colRole')}</th>
                <th>{t('admin.userManagement.colStatus')}</th>
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
                        {u.email_verified
                          ? t('admin.userManagement.statusVerified')
                          : t('admin.userManagement.statusUnverified')}
                      </span>
                    </td>
                    <td>
                      <select
                        className="form-input w-[130px] p-1"
                        value={deriveHighestRole(currentRoles)}
                        onChange={(e) => handleRoleChange(u.id, e.target.value, currentRoles)}
                        disabled={roleMutation.isPending || !roles}
                        aria-label={t('admin.userManagement.roleAriaLabel', {
                          name: u.display_name ?? u.email,
                        })}
                      >
                        {roleOptions.map((r) => (
                          <option key={r} value={r}>
                            {titleCase(r)}
                          </option>
                        ))}
                      </select>
                      {roleError?.userId === u.id && (
                        <p className="error-text mt-1 max-w-[180px]" role="alert">
                          {roleError.message}
                        </p>
                      )}
                    </td>
                    <td>
                      <span className={u.is_active ? 'text-active' : 'text-suspended'}>
                        {u.is_active
                          ? t('admin.userManagement.statusActive')
                          : t('admin.userManagement.statusInactive')}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          {data.items.length === 0 && <p>{t('admin.userManagement.noUsers')}</p>}

          <div className="pagination">
            <button disabled={cursorStack.length <= 1} onClick={goPrev}>
              {t('common.previous')}
            </button>
            <button disabled={!data.next_cursor} onClick={goNext}>
              {t('common.next')}
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
              {t('admin.userManagement.userDetail')}
            </h3>
            <div className="grid gap-3" style={{ gridTemplateColumns: '1fr 1fr' }}>
              <DetailField label={t('admin.userManagement.detailName')} value={userDetail.display_name ?? '—'} />
              <DetailField label={t('admin.userManagement.detailEmail')} value={userDetail.email} />
              <DetailField
                label={t('admin.userManagement.detailEmailVerified')}
                value={userDetail.email_verified ? t('admin.userManagement.yes') : t('admin.userManagement.no')}
              />
              <DetailField
                label={t('admin.userManagement.detailStatus')}
                value={
                  userDetail.is_active
                    ? t('admin.userManagement.statusActive')
                    : t('admin.userManagement.statusInactive')
                }
              />
              <DetailField label={t('admin.userManagement.detailLocale')} value={userDetail.locale ?? '—'} />
              <DetailField
                label={t('admin.userManagement.detailRoles')}
                value={userDetail.roles?.length ? userDetail.roles.join(', ') : '—'}
              />
              <DetailField
                label={t('admin.userManagement.detailMemberSince')}
                value={new Date(userDetail.created_at).toLocaleDateString()}
              />
            </div>
            <button
              className="btn mt-4"
              onClick={() => setDetailUserId(null)}
            >
              {t('admin.userManagement.close')}
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
