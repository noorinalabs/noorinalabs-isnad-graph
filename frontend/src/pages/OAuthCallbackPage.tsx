import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

export default function OAuthCallbackPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  useEffect(() => {
    const state = searchParams.get('state')
    const code = searchParams.get('code')
    const storedState = sessionStorage.getItem('oauth_state')

    // State validation is mandatory — reject if no stored state
    if (!storedState) {
      sessionStorage.removeItem('oauth_state')
      navigate('/login?error=missing_state', { replace: true })
      return
    }

    if (!state || state !== storedState) {
      sessionStorage.removeItem('oauth_state')
      navigate('/login?error=state_mismatch', { replace: true })
      return
    }

    // Clean up stored state (one-time use)
    sessionStorage.removeItem('oauth_state')

    if (!code) {
      navigate('/login?error=missing_code', { replace: true })
      return
    }

    // Extract provider from the current path (e.g., /auth/callback/google)
    const pathParts = window.location.pathname.split('/')
    const provider = pathParts[pathParts.length - 1] || 'unknown'

    // The backend callback handles the code exchange via the cookie-based flow.
    // Redirect to the backend callback endpoint which will set auth cookies.
    window.location.href =
      \`/api/v1/auth/callback/\${provider}?code=\${encodeURIComponent(code)}&state=\${encodeURIComponent(state)}\`
  }, [searchParams, navigate])

  return (
    <div style={{ padding: '2rem', textAlign: 'center' }}>
      <p>Completing authentication...</p>
    </div>
  )
}
