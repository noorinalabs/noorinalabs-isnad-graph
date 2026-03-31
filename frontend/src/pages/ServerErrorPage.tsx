import { Link } from 'react-router-dom'

export default function ServerErrorPage() {
  return (
    <div className="error-page">
      {/* Broken graph edges icon */}
      <div className="empty-state-icon">
        <svg width="80" height="80" viewBox="0 0 80 80" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <circle cx="25" cy="25" r="5" />
          <circle cx="55" cy="25" r="5" />
          <circle cx="40" cy="55" r="5" />
          <circle cx="15" cy="55" r="5" />
          {/* Jagged/broken edges */}
          <polyline points="30,25 36,22 38,28 42,22 44,28 50,25" />
          <polyline points="27,30 30,35 26,38 32,42 28,46 38,50" />
          <polyline points="53,30 50,38 54,42 48,48 42,50" />
        </svg>
      </div>
      <div className="error-page-code">500</div>
      <div className="error-page-title">Something went wrong</div>
      <div className="error-page-body">
        An unexpected error occurred. Please try again.
      </div>
      <Link to="/" className="btn-primary" style={{ textDecoration: 'none' }}>
        Return home
      </Link>
    </div>
  )
}
