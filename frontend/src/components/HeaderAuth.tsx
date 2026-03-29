import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import styles from './HeaderAuth.module.css'

export default function HeaderAuth() {
  const { user, isAdmin, isAuthenticated, logout } = useAuth()

  if (!isAuthenticated) {
    return (
      <div className={styles.container}>
        <Link to="/login" className={styles.loginLink}>
          Login
        </Link>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <span className={styles.userName}>{user!.name || user!.email}</span>
      {isAdmin && (
        <Link to="/admin" className="badge-admin">
          Admin
        </Link>
      )}
      <button
        type="button"
        className={styles.logoutButton}
        onClick={() => void logout()}
        aria-label="Log out"
      >
        Logout
      </button>
    </div>
  )
}
