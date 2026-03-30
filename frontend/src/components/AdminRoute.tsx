import { Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function AdminRoute() {
  const { isAdmin } = useAuth()

  if (!isAdmin) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <h1 className="text-4xl font-bold">403</h1>
        <p className="text-muted-foreground">You do not have permission to access this page.</p>
      </div>
    )
  }

  return <Outlet />
}
