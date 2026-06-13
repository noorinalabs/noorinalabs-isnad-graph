import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
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
  GeometricBorder,
} from '@noorinalabs/design-system'

// `labelKey` indexes into the `nav.*` translation namespace; resolved at render
// time so the sidebar re-labels live when the UI language changes.
const navItems = [
  { to: '/narrators', labelKey: 'nav.narrators', Icon: NarratorsIcon },
  { to: '/hadiths', labelKey: 'nav.hadiths', Icon: HadithsIcon },
  { to: '/collections', labelKey: 'nav.collections', Icon: CollectionsIcon },
  { to: '/search', labelKey: 'nav.search', Icon: SearchIcon },
  { to: '/timeline', labelKey: 'nav.timeline', Icon: TimelineIcon },
  { to: '/compare', labelKey: 'nav.compare', Icon: CompareIcon },
  { to: '/graph', labelKey: 'nav.graphExplorer', Icon: GraphExplorerIcon },
] as const

export default function Sidebar() {
  const { t } = useTranslation()
  const { user, isAdmin, signOut } = useAuth()

  return (
    <nav
      aria-label={t('nav.ariaLabel')}
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
              {t(item.labelKey)}
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
              {t('nav.adminDashboard')}
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
            {t('nav.signOut')}
          </button>
        </div>
      )}
    </nav>
  )
}
