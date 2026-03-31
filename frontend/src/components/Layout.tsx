import { Link, Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import UserMenu from './UserMenu'
import { PageHeaderAccent } from './icons/decorative'

export default function Layout() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <header
        className="geo-border-bottom"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--spacing-4)',
          padding: 'var(--spacing-3) var(--spacing-6)',
          background: 'var(--color-card)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--spacing-3)',
            flex: 1,
          }}
        >
          <PageHeaderAccent style={{ display: 'inline-block', verticalAlign: 'middle' }} />
          <a
            href="https://www.noorinalabs.com"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              margin: 0,
              fontSize: 'var(--text-lg)',
              fontFamily: 'var(--font-heading)',
              fontWeight: 400,
              color: 'var(--color-muted-foreground)',
              letterSpacing: 'var(--tracking-tight)',
              textDecoration: 'none',
              transition: 'color var(--duration-fast) var(--ease-default)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--color-primary)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--color-muted-foreground)'
            }}
          >
            NoorinaLabs
          </a>
          <span
            style={{
              color: 'var(--color-border)',
              fontSize: 'var(--text-lg)',
              fontWeight: 300,
              userSelect: 'none',
            }}
            aria-hidden="true"
          >
            |
          </span>
          <Link
            to="/"
            style={{
              margin: 0,
              fontSize: 'var(--text-xl)',
              fontFamily: 'var(--font-heading)',
              fontWeight: 600,
              color: 'var(--color-primary)',
              letterSpacing: 'var(--tracking-tight)',
              textDecoration: 'none',
            }}
          >
            Isnad Graph
          </Link>
        </div>
        <span className="small-muted" style={{ fontFamily: 'var(--font-heading)' }}>
          Hadith Analysis Platform
        </span>
        <UserMenu />
      </header>
      <div style={{ display: 'flex', flex: 1 }}>
        <Sidebar />
        <main style={{ flex: 1, padding: 'var(--spacing-6)', overflow: 'auto' }}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
