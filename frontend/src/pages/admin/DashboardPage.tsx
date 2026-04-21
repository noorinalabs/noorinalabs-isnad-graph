import { useQuery } from '@tanstack/react-query'
import { fetchDashboardStats } from '../../api/admin-client'

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div
      style={{
        padding: 'var(--spacing-4)',
        background: 'var(--color-card)',
        border: 'var(--border-width-thin) solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
      }}
    >
      <div
        style={{
          fontSize: 'var(--text-xs)',
          color: 'var(--color-muted-foreground)',
          marginBottom: 'var(--spacing-1)',
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 'var(--text-2xl)',
          fontWeight: 700,
          fontFamily: 'var(--font-heading)',
          color: 'var(--color-foreground)',
        }}
      >
        {value}
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-dashboard-stats'],
    queryFn: fetchDashboardStats,
  })

  if (isLoading) return <p>Loading dashboard...</p>
  if (error) return <p className="error-text">Error: {(error as Error).message}</p>
  if (!data) return null

  const hasUserStats =
    data.total_users !== undefined ||
    data.active_users !== undefined ||
    data.suspended_users !== undefined ||
    data.new_registrations_7d !== undefined

  return (
    <div>
      <h2>Admin Dashboard</h2>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 'var(--spacing-4)',
          marginBottom: 'var(--spacing-6)',
          marginTop: 'var(--spacing-4)',
        }}
      >
        {data.total_users !== undefined && (
          <StatCard label="Total Users" value={data.total_users} />
        )}
        {data.active_users !== undefined && (
          <StatCard label="Active Users" value={data.active_users} />
        )}
        {data.suspended_users !== undefined && (
          <StatCard label="Suspended Users" value={data.suspended_users} />
        )}
        {data.new_registrations_7d !== undefined && (
          <StatCard label="New (7d)" value={data.new_registrations_7d} />
        )}
        <StatCard label="Active Sessions" value={data.active_sessions} />
      </div>

      {data.users_by_role && data.users_by_role.length > 0 ? (
        <>
          <h3
            style={{
              fontFamily: 'var(--font-heading)',
              fontSize: 'var(--text-base)',
              marginBottom: 'var(--spacing-3)',
            }}
          >
            Users by Role
          </h3>
          <table className="data-table" style={{ maxWidth: 400 }}>
            <thead>
              <tr>
                <th>Role</th>
                <th>Count</th>
              </tr>
            </thead>
            <tbody>
              {data.users_by_role.map((rc) => (
                <tr key={rc.role}>
                  <td style={{ textTransform: 'capitalize' }}>{rc.role}</td>
                  <td>{rc.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : (
        !hasUserStats && (
          <div
            style={{
              padding: 'var(--spacing-4)',
              background: 'var(--color-card)',
              border: 'var(--border-width-thin) solid var(--color-border)',
              borderRadius: 'var(--radius-lg)',
              color: 'var(--color-muted-foreground)',
              fontSize: 'var(--text-sm)',
            }}
          >
            User statistics have moved to user-service. This panel will return once the
            cross-service admin API lands (see #806).
          </div>
        )
      )}
    </div>
  )
}
