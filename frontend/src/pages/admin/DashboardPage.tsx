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
        <StatCard label="Total Users" value={data.total_users} />
        <StatCard label="Active Users" value={data.active_users} />
        <StatCard label="Suspended Users" value={data.suspended_users} />
        <StatCard label="New (7d)" value={data.new_registrations_7d} />
        <StatCard label="Active Sessions" value={data.active_sessions} />
      </div>

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
          {data.users_by_role.length === 0 && (
            <tr>
              <td colSpan={2} style={{ textAlign: 'center', color: 'var(--color-muted-foreground)' }}>
                No data
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
