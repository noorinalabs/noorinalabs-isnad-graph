import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/Tabs'
import { Input } from '../components/ui/Input'
import { Button } from '../components/ui/Button'

const API_BASE = '/api/v1'

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  )
}

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      aria-hidden="true"
    >
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
    </svg>
  )
}

function validateEmail(email: string): string | null {
  if (!email) return 'Email is required'
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return 'Invalid email address'
  return null
}

function validatePassword(password: string): string | null {
  if (!password) return 'Password is required'
  if (password.length < 8) return 'Password must be at least 8 characters'
  return null
}

export default function LoginPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const from = (location.state as { from?: string })?.from || '/'

  const [error, setError] = useState<string | null>(null)
  const [oauthLoading, setOauthLoading] = useState<string | null>(null)
  const [formLoading, setFormLoading] = useState(false)

  // Sign-in form state
  const [loginEmail, setLoginEmail] = useState('')
  const [loginPassword, setLoginPassword] = useState('')

  // Register form state
  const [regName, setRegName] = useState('')
  const [regEmail, setRegEmail] = useState('')
  const [regPassword, setRegPassword] = useState('')
  const [regConfirm, setRegConfirm] = useState('')

  async function handleOAuth(provider: 'google' | 'github') {
    setError(null)
    setOauthLoading(provider)

    try {
      const res = await fetch(`${API_BASE}/auth/login/${provider}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
        throw new Error(data.detail || `Failed to initiate ${provider} login`)
      }

      const data = await res.json()
      sessionStorage.setItem('oauth_return_url', from)
      window.location.href = data.authorization_url
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
      setOauthLoading(null)
    }
  }

  async function handleEmailLogin(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    const emailErr = validateEmail(loginEmail)
    if (emailErr) { setError(emailErr); return }
    const pwErr = validatePassword(loginPassword)
    if (pwErr) { setError(pwErr); return }

    setFormLoading(true)
    try {
      const res = await fetch(`${API_BASE}/auth/login/email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginEmail, password: loginPassword }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
        throw new Error(data.detail || 'Invalid credentials')
      }

      const data = await res.json()
      localStorage.setItem('access_token', data.access_token)
      if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setFormLoading(false)
    }
  }

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (!regName.trim()) { setError('Name is required'); return }
    const emailErr = validateEmail(regEmail)
    if (emailErr) { setError(emailErr); return }
    const pwErr = validatePassword(regPassword)
    if (pwErr) { setError(pwErr); return }
    if (regPassword !== regConfirm) { setError('Passwords do not match'); return }

    setFormLoading(true)
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: regName.trim(),
          email: regEmail,
          password: regPassword,
        }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
        throw new Error(data.detail || 'Registration failed')
      }

      const data = await res.json()
      localStorage.setItem('access_token', data.access_token)
      if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setFormLoading(false)
    }
  }

  const isLoading = oauthLoading !== null || formLoading

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-sm space-y-6 rounded-2xl border border-border bg-card p-10 shadow-xl">
        {/* Geometric accent line */}
        <div className="geo-border-top" />

        <div className="text-center space-y-3">
          {/* Octagonal icon placeholder */}
          <div
            className="mx-auto flex items-center justify-center"
            style={{
              width: 56,
              height: 56,
              borderRadius: 'var(--radius-lg)',
              background: 'var(--color-primary)',
              color: 'var(--color-primary-foreground)',
              transform: 'rotate(0deg)',
            }}
          >
            <svg width="28" height="28" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="10" cy="10" r="3" />
              <circle cx="22" cy="10" r="3" />
              <circle cx="16" cy="22" r="3" />
              <line x1="13" y1="10" x2="19" y2="10" />
              <line x1="11" y1="13" x2="15" y2="19" />
              <line x1="21" y1="13" x2="17" y2="19" />
            </svg>
          </div>
          <h1 className="text-2xl font-semibold" style={{ fontFamily: 'var(--font-heading)', color: 'var(--color-foreground)' }}>
            Isnad Graph
          </h1>
          <p className="text-sm text-muted-foreground">
            Sign in to access the hadith analysis platform
          </p>
        </div>

        {error && (
          <div
            role="alert"
            className="rounded-lg border border-destructive bg-destructive/10 px-4 py-3 text-sm text-destructive"
          >
            {error}
          </div>
        )}

        {/* OAuth Buttons */}
        <div className="space-y-3">
          <button
            onClick={() => handleOAuth('google')}
            disabled={isLoading}
            className="flex w-full items-center justify-center gap-3 rounded-md border border-[#dadce0] bg-white px-4 py-2.5 text-sm font-medium text-[#3c4043] shadow-sm hover:bg-[#f8f9fa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#4285f4] transition-colors disabled:opacity-50 dark:border-[#5f6368] dark:bg-[#131314] dark:text-[#e3e3e3] dark:hover:bg-[#1f1f1f]"
          >
            <GoogleIcon />
            {oauthLoading === 'google' ? 'Redirecting...' : 'Sign in with Google'}
          </button>

          <button
            onClick={() => handleOAuth('github')}
            disabled={isLoading}
            className="flex w-full items-center justify-center gap-3 rounded-md bg-[#24292f] px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-[#32383f] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#24292f] transition-colors disabled:opacity-50 dark:bg-[#f0f0f0] dark:text-[#24292f] dark:hover:bg-[#d4d4d4]"
          >
            <GitHubIcon className="dark:text-[#24292f]" />
            {oauthLoading === 'github' ? 'Redirecting...' : 'Sign in with GitHub'}
          </button>
        </div>

        {/* Divider */}
        <div className="relative flex items-center">
          <div className="flex-1 border-t border-border" />
          <span className="px-3 text-xs text-muted-foreground uppercase">or</span>
          <div className="flex-1 border-t border-border" />
        </div>

        {/* Email/Password Tabs */}
        <Tabs defaultValue="signin" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="signin" disabled={isLoading}>
              Sign in
            </TabsTrigger>
            <TabsTrigger value="register" disabled={isLoading}>
              Create account
            </TabsTrigger>
          </TabsList>

          <TabsContent value="signin">
            <form onSubmit={handleEmailLogin} className="space-y-4 pt-2">
              <div className="space-y-2">
                <label htmlFor="login-email" className="text-sm font-medium">
                  Email
                </label>
                <Input
                  id="login-email"
                  type="email"
                  placeholder="you@example.com"
                  autoComplete="email"
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  disabled={isLoading}
                  required
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="login-password" className="text-sm font-medium">
                  Password
                </label>
                <Input
                  id="login-password"
                  type="password"
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  disabled={isLoading}
                  required
                />
              </div>
              <Button type="submit" className="w-full" disabled={isLoading}>
                {formLoading ? 'Signing in...' : 'Sign in'}
              </Button>
            </form>
          </TabsContent>

          <TabsContent value="register">
            <form onSubmit={handleRegister} className="space-y-4 pt-2">
              <div className="space-y-2">
                <label htmlFor="reg-name" className="text-sm font-medium">
                  Name
                </label>
                <Input
                  id="reg-name"
                  type="text"
                  placeholder="Your name"
                  autoComplete="name"
                  value={regName}
                  onChange={(e) => setRegName(e.target.value)}
                  disabled={isLoading}
                  required
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="reg-email" className="text-sm font-medium">
                  Email
                </label>
                <Input
                  id="reg-email"
                  type="email"
                  placeholder="you@example.com"
                  autoComplete="email"
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  disabled={isLoading}
                  required
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="reg-password" className="text-sm font-medium">
                  Password
                </label>
                <Input
                  id="reg-password"
                  type="password"
                  placeholder="At least 8 characters"
                  autoComplete="new-password"
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  disabled={isLoading}
                  required
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="reg-confirm" className="text-sm font-medium">
                  Confirm password
                </label>
                <Input
                  id="reg-confirm"
                  type="password"
                  placeholder="Re-enter your password"
                  autoComplete="new-password"
                  value={regConfirm}
                  onChange={(e) => setRegConfirm(e.target.value)}
                  disabled={isLoading}
                  required
                />
              </div>
              <Button type="submit" className="w-full" disabled={isLoading}>
                {formLoading ? 'Creating account...' : 'Create account'}
              </Button>
            </form>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
