import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="error-page">
      {/* Disconnected graph node icon */}
      <div className="empty-state-icon">
        <svg width="80" height="80" viewBox="0 0 80 80" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <circle cx="25" cy="25" r="5" />
          <circle cx="55" cy="25" r="5" />
          <circle cx="40" cy="55" r="5" />
          {/* Broken edge */}
          <line x1="30" y1="25" x2="38" y2="25" />
          <line x1="42" y1="25" x2="50" y2="25" />
          {/* Intact edges */}
          <line x1="27" y1="30" x2="38" y2="50" />
          <line x1="53" y1="30" x2="42" y2="50" />
          {/* Drifting disconnected node */}
          <circle cx="65" cy="60" r="4" opacity="0.4" strokeDasharray="3 2" />
        </svg>
      </div>
      <div className="error-page-code">404</div>
      <div className="error-page-title">Page not found</div>
      <div className="error-page-body">
        The page you are looking for does not exist or has been moved.
      </div>
      <Link to="/" className="btn-primary" style={{ textDecoration: 'none' }}>
        Return home
      </Link>
    </div>
  )
}
