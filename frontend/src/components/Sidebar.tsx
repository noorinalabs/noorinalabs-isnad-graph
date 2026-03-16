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
    <nav style={{ width: 220, padding: '1rem', borderRight: '1px solid #ddd' }}>
      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {navItems.map((item) => (
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
        {isAdmin && (
          <li style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #ddd' }}>
            <NavLink
              to="/admin"
              style={({ isActive }) => ({
                textDecoration: 'none',
                fontWeight: isActive ? 700 : 400,
                color: isActive ? '#1a73e8' : '#333',
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
