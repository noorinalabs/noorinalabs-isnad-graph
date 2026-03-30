import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

export default function AuthCallbackPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  useEffect(() => {
    const token = searchParams.get('token')
    const refreshToken = searchParams.get('refresh_token')
    const returnUrl = sessionStorage.getItem('oauth_return_url') || '/'

    if (token) {
      localStorage.setItem('access_token', token)
    }
    if (refreshToken) {
      localStorage.setItem('refresh_token', refreshToken)
    }
    sessionStorage.removeItem('oauth_return_url')

    navigate(returnUrl, { replace: true })
  }, [searchParams, navigate])

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary border-t-transparent" />
    </div>
  )
}
