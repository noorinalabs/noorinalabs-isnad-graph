import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useSubscription } from '../hooks/useSubscription'

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary border-t-transparent" />
    </div>
  )
}

export default function ProtectedRoute() {
  const { user, loading } = useAuth()
  const { isExpired, isLoading: subLoading } = useSubscription()
  const location = useLocation()

  // Auth must resolve before we can decide whether to redirect or render.
  if (loading) {
    return <LoadingSpinner />
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }

  if (isExpired) {
    return <Navigate to="/trial-expired" replace />
  }

  if (!user.email_verified) {
    return <Navigate to="/check-email" replace />
  }

  // Once authenticated, the child subtree mounts once and stays mounted.
  // A `subLoading` toggle renders an overlay alongside <Outlet /> rather than
  // swapping it out — otherwise React unmounts/remounts the whole subtree on
  // every toggle, amplifying any re-mount-driven retry loop (see #831, #830).
  return (
    <>
      <Outlet />
      {subLoading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/60 backdrop-blur-sm">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary border-t-transparent" />
        </div>
      )}
    </>
  )
}
