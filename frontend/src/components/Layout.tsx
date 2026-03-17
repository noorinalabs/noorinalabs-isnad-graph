import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'

export default function Layout() {
  return (
    <div className="flex-row" style={{ flexDirection: 'column', minHeight: '100vh', alignItems: 'stretch' }}>
      <header className="flex-row" style={{ padding: '0.75rem 1.5rem', borderBottom: '1px solid #ddd' }}>
        <h1 style={{ margin: 0, fontSize: '1.25rem' }}>Isnad Graph</h1>
        <span className="small-muted">Hadith Analysis Platform</span>
      </header>
      <div style={{ display: 'flex', flex: 1 }}>
        <Sidebar />
        <main style={{ flex: 1, padding: '1.5rem' }}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
