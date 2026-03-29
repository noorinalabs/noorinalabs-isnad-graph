import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

export default function OAuthCallbackPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const state = searchParams.get('state')
    const code = searchParams.get('code')
    const storedState = sessionStorage.getItem('oauth_state')

    // State validation is mandatory — reject if no stored state
    if (!storedState) {
      setError('Missing OAuth state. Please start the login flow again.')
      sessionStorage.removeItem('oauth_state')
      navigate('/login?error=missing_state', { replace: true })
      return
    }

    if (!state || state !== storedState) {
      setError('OAuth state mismatch. Please start the login flow again.')
      sessionStorage.removeItem('oauth_state')
      navigate('/login?error=state_mismatch', { replace: true })
      return
    }

    // Clean up stored state (one-time use)
    sessionStorage.removeItem('oauth_state')

    if (!code) {
      setError('Missing authorization code.')
      navigate('/login?error=missing_code', { replace: true })
      return
    }

    // Extract provider from the current path (e.g., /auth/callback/google)
    const pathParts = window.location.pathname.split('/')
    const provider = pathParts[pathParts.length - 1] || 'unknown'

    // The backend callback handles the code exchange via the cookie-based flow.
    // Redirect to the backend callback endpoint which will set auth cookies.
    window.location.href =
      `/api/v1/auth/callback/${provider}?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`
  }, [searchParams, navigate])

  if (error) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        <h2>Authentication Error</h2>
        <p>{error}</p>
        <a href="/login">Return to Login</a>
      </div>
    )
  }

  return (
    <div style={{ padding: '2rem', textAlign: 'center' }}>
      <p>Completing authentication...</p>
    </div>
  )
}
