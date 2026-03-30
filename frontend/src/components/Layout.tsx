import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import ThemeToggle from './ThemeToggle'

export default function Layout() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--spacing-3)',
          padding: 'var(--spacing-3) var(--spacing-6)',
          borderBottom: 'var(--border-width-thin) solid var(--color-border)',
          background: 'var(--color-card)',
        }}
      >
        <h1 style={{ margin: 0, fontSize: 'var(--text-xl)', fontFamily: 'var(--font-heading)', flex: 1 }}>
          Isnad Graph
        </h1>
        <span className="small-muted">Hadith Analysis Platform</span>
        <ThemeToggle />
      </header>
      <div style={{ display: 'flex', flex: 1 }}>
        <Sidebar />
        <main style={{ flex: 1, padding: 'var(--spacing-6)' }}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
