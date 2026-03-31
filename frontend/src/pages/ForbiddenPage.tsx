import { Link } from 'react-router-dom'

export default function ForbiddenPage() {
  return (
    <div className="error-page">
      {/* Locked node icon */}
      <div className="empty-state-icon">
        <svg width="80" height="80" viewBox="0 0 80 80" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          {/* Lock body */}
          <rect x="28" y="38" width="24" height="18" rx="3" />
          {/* Lock shackle */}
          <path d="M34 38V30a6 6 0 0 1 12 0v8" />
          {/* Keyhole */}
          <circle cx="40" cy="47" r="2" />
          <line x1="40" y1="49" x2="40" y2="52" />
        </svg>
      </div>
      <div className="error-page-code">403</div>
      <div className="error-page-title">Access denied</div>
      <div className="error-page-body">
        You do not have permission to access this page.
      </div>
      <Link to="/" className="btn-primary" style={{ textDecoration: 'none' }}>
        Return home
      </Link>
    </div>
  )
}
