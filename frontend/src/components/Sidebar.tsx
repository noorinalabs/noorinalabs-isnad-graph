import { NavLink } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import {
  NarratorsIcon,
  HadithsIcon,
  CollectionsIcon,
  SearchIcon,
  TimelineIcon,
  CompareIcon,
  GraphExplorerIcon,
  AdminIcon,
  SignOutIcon,
} from './icons'
import { GeometricBorder } from './icons/decorative'

const navItems = [
  { to: '/narrators', label: 'Narrators', Icon: NarratorsIcon },
  { to: '/hadiths', label: 'Hadiths', Icon: HadithsIcon },
  { to: '/collections', label: 'Collections', Icon: CollectionsIcon },
  { to: '/search', label: 'Search', Icon: SearchIcon },
  { to: '/timeline', label: 'Timeline', Icon: TimelineIcon },
  { to: '/compare', label: 'Compare', Icon: CompareIcon },
  { to: '/graph', label: 'Graph Explorer', Icon: GraphExplorerIcon },
]

export default function Sidebar() {
  const { user, isAdmin, signOut } = useAuth()

  return (
    <nav
      aria-label="Main navigation"
      style={{
        width: 240,
        padding: 'var(--spacing-4)',
        borderInlineEnd: 'var(--border-width-thin) solid var(--color-border)',
        background: 'var(--color-card)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <ul style={{ listStyle: 'none', padding: 0, margin: 0, flex: 1 }}>
        {navItems.map((item) => (
          <li key={item.to} style={{ marginBottom: 'var(--spacing-1)' }}>
            <NavLink
              to={item.to}
              style={({ isActive }) => ({
                textDecoration: 'none',
                fontWeight: isActive ? 600 : 400,
                color: isActive ? 'var(--color-primary)' : 'var(--color-foreground)',
                fontFamily: 'var(--font-body)',
                fontSize: 'var(--text-sm)',
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--spacing-2_5)',
                padding: 'var(--spacing-2) var(--spacing-3)',
                borderRadius: 'var(--radius-md)',
                background: isActive ? 'var(--color-accent)' : 'transparent',
                borderInlineStart: isActive
                  ? '3px solid var(--color-primary)'
                  : '3px solid transparent',
                transition: 'all var(--duration-fast) var(--ease-default)',
              })}
            >
              <item.Icon size={16} style={{ flexShrink: 0, opacity: 0.7 }} />
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
                fontWeight: isActive ? 600 : 400,
                color: isActive ? 'var(--color-primary)' : 'var(--color-foreground)',
                fontFamily: 'var(--font-body)',
                fontSize: 'var(--text-sm)',
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--spacing-2_5)',
                padding: 'var(--spacing-2) var(--spacing-3)',
                borderRadius: 'var(--radius-md)',
                background: isActive ? 'var(--color-accent)' : 'transparent',
                borderInlineStart: isActive
                  ? '3px solid var(--color-primary)'
                  : '3px solid transparent',
              })}
            >
              <AdminIcon size={16} style={{ flexShrink: 0, opacity: 0.7 }} />
              Admin Dashboard
            </NavLink>
          </li>
        )}
      </ul>

      {/* Geometric divider above user section */}
      <GeometricBorder style={{ marginBottom: 'var(--spacing-3)' }} />

      {user && (
        <div>
          <div
            style={{
              fontSize: 'var(--text-xs)',
              color: 'var(--color-muted-foreground)',
              marginBottom: 'var(--spacing-2)',
              paddingInline: 'var(--spacing-3)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={user.email}
          >
            {user.display_name ?? user.email}
          </div>
          <button
            onClick={signOut}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--spacing-2)',
              padding: 'var(--spacing-1_5) var(--spacing-3)',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              background: 'transparent',
              color: 'var(--color-foreground)',
              fontFamily: 'var(--font-body)',
              fontSize: 'var(--text-sm)',
              cursor: 'pointer',
              transition: 'background-color var(--duration-fast) var(--ease-default)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--color-accent)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
            }}
          >
            <SignOutIcon size={16} />
            Sign out
          </button>
        </div>
      )}
    </nav>
  )
}
