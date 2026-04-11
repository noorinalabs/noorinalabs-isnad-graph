import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const API_BASE = '/api/v1'

const POLL_INTERVAL_MS = 30_000

export default function CheckEmailPage() {
  const { user, loading, signOut, refreshUser } = useAuth()
  const navigate = useNavigate()
  const [resending, setResending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cooldown, setCooldown] = useState(0)

  useEffect(() => {
    if (!loading && user?.email_verified) {
      navigate('/', { replace: true })
    }
  }, [user, loading, navigate])

  // Poll for verification status changes (e.g. verified in another tab)
  useEffect(() => {
    if (loading || !user || user.email_verified) return
    const id = setInterval(refreshUser, POLL_INTERVAL_MS)
    return () => clearInterval(id)
  }, [loading, user, refreshUser])

  useEffect(() => {
    if (cooldown <= 0) return
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => clearTimeout(timer)
  }, [cooldown])

  const handleResend = useCallback(async () => {
    setResending(true)
    setError(null)
    setMessage(null)

    try {
      const token = localStorage.getItem('access_token')
      const res = await fetch(`${API_BASE}/verification/send`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      })

      if (res.status === 429) {
        setError('Too many requests. Please wait before trying again.')
        setCooldown(60)
        return
      }

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: 'Failed to resend' }))
        throw new Error(data.detail || 'Failed to resend verification email')
      }

      setMessage('Verification email sent! Check your inbox.')
      setCooldown(60)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resend')
    } finally {
      setResending(false)
    }
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-md space-y-6 rounded-2xl border border-border bg-card p-10 shadow-xl text-center">
        <div className="geo-border-top" />

        <div
          className="mx-auto flex items-center justify-center"
          style={{
            width: 64,
            height: 64,
            borderRadius: 'var(--radius-lg)',
            background: 'var(--color-primary)',
            color: 'var(--color-primary-foreground)',
          }}
        >
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="4" width="20" height="16" rx="2" />
            <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
          </svg>
        </div>

        <div className="space-y-2">
          <h1 className="text-2xl font-semibold" style={{ fontFamily: 'var(--font-heading)' }}>
            Check your email
          </h1>
          <p className="text-sm text-muted-foreground">
            We sent a verification email to{' '}
            <strong className="text-foreground">{user?.email}</strong>.
          </p>
          <p className="text-sm text-muted-foreground">
            Click the link in the email and enter the 6-digit code to verify your account.
          </p>
        </div>

        {message && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-3 text-sm text-green-700 dark:text-green-400">
            {message}
          </div>
        )}

        {error && (
          <div role="alert" className="rounded-lg border border-destructive bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="space-y-3">
          <button
            onClick={handleResend}
            disabled={resending || cooldown > 0}
            className="inline-flex w-full items-center justify-center rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {resending
              ? 'Sending...'
              : cooldown > 0
                ? `Resend in ${cooldown}s`
                : 'Resend verification email'}
          </button>

          <button
            onClick={() => signOut()}
            className="inline-flex w-full items-center justify-center rounded-md border border-border px-4 py-2.5 text-sm font-medium text-foreground hover:bg-muted transition-colors"
          >
            Sign out
          </button>
        </div>

        <p className="text-xs text-muted-foreground">
          Didn't receive the email? Check your spam folder or click resend above.
        </p>
      </div>
    </div>
  )
}
