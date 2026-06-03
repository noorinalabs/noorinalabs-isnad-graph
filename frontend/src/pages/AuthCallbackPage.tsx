import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

const ERROR_MESSAGES: Record<string, string> = {
  oauth_exchange_failed:
    'Unable to complete sign-in with the provider. The provider may be temporarily unavailable. Please try again.',
  account_suspended:
    'Your account has been suspended. Please contact support for assistance.',
  email_mismatch:
    'The email from the provider does not match any existing account. Please use the correct provider.',
}

export default function AuthCallbackPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const errorCode = searchParams.get('error')
    // The access token is read ONLY from the URL fragment. user-service delivers
    // it in the fragment (#68) because query params leak into server logs, the
    // Referer header, and browser history. The `?token=` query fallback that PR
    // #952 kept for the pre-#68 transition is now removed (#955): us#147 is
    // deployed, so the backend always sends the token in the fragment. Keeping a
    // query read alive would re-open the very Referer-leak path #68 closed — a
    // token arriving on the query string is now treated as untrusted and ignored.
    const token = new URLSearchParams(window.location.hash.slice(1)).get('token')
    const isNewUser = searchParams.get('is_new_user')
    const needsVerification = searchParams.get('needs_verification')
    const returnUrl = sessionStorage.getItem('oauth_return_url') || '/'

    if (errorCode) {
      setError(ERROR_MESSAGES[errorCode] || `Authentication failed (${errorCode}). Please try again.`)
      return
    }

    if (token) {
      localStorage.setItem('access_token', token)
    }

    // Store new-user flag for onboarding prompt
    if (isNewUser === '1') {
      sessionStorage.setItem('is_new_user', '1')
    }

    // Refresh token is now in an httpOnly cookie (set by the server redirect).
    // No need to store it in localStorage.

    sessionStorage.removeItem('oauth_return_url')

    // Redirect to email verification for new users
    if (needsVerification === '1') {
      navigate('/check-email', { replace: true })
      return
    }

    navigate(returnUrl, { replace: true })
  }, [searchParams, navigate])

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="w-full max-w-md space-y-4 rounded-2xl border border-border bg-card p-8 shadow-xl text-center">
          <div
            className="mx-auto flex items-center justify-center rounded-full"
            style={{
              width: 48,
              height: 48,
              background: 'var(--color-destructive)',
              color: 'var(--color-destructive-foreground, #fff)',
            }}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-foreground">Sign-in failed</h2>
          <p className="text-sm text-muted-foreground">{error}</p>
          <button
            onClick={() => { window.location.href = '/login' }}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Back to sign in
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary border-t-transparent" />
    </div>
  )
}
