import { NavLink, Outlet, Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import ThemeToggle from './ThemeToggle'
import styles from './AdminLayout.module.css'

const adminNavItems = [
  { to: '/admin/users', label: 'User Management' },
  { to: '/admin/health', label: 'System Health' },
  { to: '/admin/stats', label: 'Content Stats' },
  { to: '/admin/analytics', label: 'Usage Analytics' },
]

export default function AdminLayout() {
  const { user, loading, isAdmin } = useAuth()

  if (loading) {
    return <p className={styles.loading}>Loading...</p>
  }

  if (!user || !isAdmin) {
    return <Navigate to="/narrators" replace />
  }

  return (
    <div className={styles.wrapper}>
      <header className={`flex-row ${styles.header}`}>
        <NavLink to="/" className={styles.headerLink}>
          <h1 className={styles.headerTitle}>Isnad Graph</h1>
        </NavLink>
        <span className="small-muted" style={{ flex: 1 }}>Admin Dashboard</span>
        <ThemeToggle />
      </header>
      <div className={styles.body}>
        <nav className={styles.sidebar} aria-label="Admin navigation">
          <ul className={styles.sidebarList}>
            <li className={styles.sidebarBackItem}>
              <NavLink to="/" className={`small-muted ${styles.sidebarBackLink}`}>
                Back to main site
              </NavLink>
            </li>
            {adminNavItems.map((item) => (
              <li key={item.to} className={styles.sidebarItem}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    isActive ? styles.sidebarLinkActive : styles.sidebarLink
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <main className={styles.main}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
