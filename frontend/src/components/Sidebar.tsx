import { NavLink } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const navItems = [
  { to: '/narrators', label: 'Narrators' },
  { to: '/hadiths', label: 'Hadiths' },
  { to: '/collections', label: 'Collections' },
  { to: '/search', label: 'Search' },
  { to: '/timeline', label: 'Timeline' },
  { to: '/compare', label: 'Compare' },
  { to: '/graph', label: 'Graph Explorer' },
]

export default function Sidebar() {
  const { isAdmin } = useAuth()

  return (
    <nav
      aria-label="Main navigation"
      style={{
        width: 220,
        padding: 'var(--spacing-4)',
        borderInlineEnd: 'var(--border-width-thin) solid var(--color-border)',
        background: 'var(--color-card)',
      }}
    >
      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {navItems.map((item) => (
          <li key={item.to} style={{ marginBottom: 'var(--spacing-2)' }}>
            <NavLink
              to={item.to}
              style={({ isActive }) => ({
                textDecoration: 'none',
                fontWeight: isActive ? 700 : 400,
                color: isActive ? 'var(--color-primary)' : 'var(--color-foreground)',
                fontFamily: 'var(--font-body)',
                fontSize: 'var(--text-sm)',
                display: 'block',
                padding: 'var(--spacing-1_5) var(--spacing-3)',
                borderRadius: 'var(--radius-md)',
                background: isActive ? 'var(--color-accent)' : 'transparent',
                transition: 'background-color var(--duration-fast) var(--ease-default)',
              })}
            >
              {item.label}
            </NavLink>
          </li>
        ))}
        {isAdmin && (
          <li
            style={{
              marginTop: 'var(--spacing-4)',
              paddingTop: 'var(--spacing-4)',
              borderTop: 'var(--border-width-thin) solid var(--color-border)',
            }}
          >
            <NavLink
              to="/admin"
              style={({ isActive }) => ({
                textDecoration: 'none',
                fontWeight: isActive ? 700 : 400,
                color: isActive ? 'var(--color-primary)' : 'var(--color-foreground)',
                fontFamily: 'var(--font-body)',
                fontSize: 'var(--text-sm)',
                display: 'block',
                padding: 'var(--spacing-1_5) var(--spacing-3)',
                borderRadius: 'var(--radius-md)',
                background: isActive ? 'var(--color-accent)' : 'transparent',
              })}
            >
              Admin Dashboard
            </NavLink>
          </li>
        )}
      </ul>
    </nav>
  )
}
