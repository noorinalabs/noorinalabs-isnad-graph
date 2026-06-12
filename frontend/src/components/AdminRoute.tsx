import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function AdminRoute() {
  const { hasRole, loading } = useAuth()

  // Wait for the auth context to resolve before deciding — otherwise an admin
  // who reloads on an /admin URL would be bounced to "/" during the brief
  // window where `user` is still null (hasRole('admin') === false).
  if (loading) {
    return null
  }

  // Non-admins are silently redirected home rather than shown a 403. Pairing
  // this with the API's 404 (see middleware.require_admin, ig#804), the admin
  // area is not surfaced as a forbidden-but-existing destination — it simply
  // does not exist for non-admins. The admin nav entry is likewise hidden in
  // Sidebar via `{isAdmin && ...}`.
  if (!hasRole('admin')) {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
