import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import ThemeToggle from './ThemeToggle'

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
        <h1
          style={{
            margin: 0,
            fontSize: 'var(--text-xl)',
            fontFamily: 'var(--font-heading)',
            fontWeight: 600,
            color: 'var(--color-primary)',
            letterSpacing: 'var(--tracking-tight)',
            flex: 1,
          }}
        >
          Isnad Graph
        </h1>
        <span className="small-muted" style={{ fontFamily: 'var(--font-heading)' }}>
          Hadith Analysis Platform
        </span>
        <ThemeToggle />
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
