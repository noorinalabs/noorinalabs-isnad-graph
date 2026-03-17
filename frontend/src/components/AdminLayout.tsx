import { NavLink, Outlet, Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const adminNavItems = [
  { to: '/admin/users', label: 'User Management' },
  { to: '/admin/health', label: 'System Health' },
  { to: '/admin/stats', label: 'Content Stats' },
  { to: '/admin/analytics', label: 'Usage Analytics' },
]

export default function AdminLayout() {
  const { user, loading, isAdmin } = useAuth()

  if (loading) {
    return <p style={{ padding: '2rem' }}>Loading...</p>
  }

  if (!user || !isAdmin) {
    return <Navigate to="/narrators" replace />
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <header
        className="flex-row"
        style={{ padding: '0.75rem 1.5rem', borderBottom: '1px solid #ddd', background: '#f8f9fa' }}
      >
        <NavLink to="/" style={{ textDecoration: 'none', color: 'inherit' }}>
          <h1 style={{ margin: 0, fontSize: '1.25rem' }}>Isnad Graph</h1>
        </NavLink>
        <span className="small-muted">Admin Dashboard</span>
      </header>
      <div style={{ display: 'flex', flex: 1 }}>
        <nav style={{ width: 220, padding: '1rem', borderRight: '1px solid #ddd', background: '#fafafa' }}>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            <li style={{ marginBottom: '1rem' }}>
              <NavLink to="/" className="small-muted" style={{ textDecoration: 'none' }}>
                Back to main site
              </NavLink>
            </li>
            {adminNavItems.map((item) => (
              <li key={item.to} style={{ marginBottom: '0.5rem' }}>
                <NavLink
                  to={item.to}
                  style={({ isActive }) => ({
                    textDecoration: 'none',
                    fontWeight: isActive ? 700 : 400,
                    color: isActive ? '#1a73e8' : '#333',
                  })}
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <main style={{ flex: 1, padding: '1.5rem' }}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
