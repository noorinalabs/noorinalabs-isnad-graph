import { useState, useRef, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

const API_BASE = '/api/v1'
const CODE_LENGTH = 6

export default function VerifyEmailPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''

  const [code, setCode] = useState<string[]>(Array(CODE_LENGTH).fill(''))
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const inputRefs = useRef<(HTMLInputElement | null)[]>([])

  useEffect(() => {
    inputRefs.current[0]?.focus()
  }, [])

  function handleChange(index: number, value: string) {
    if (!/^\d*$/.test(value)) return

    const newCode = [...code]
    newCode[index] = value.slice(-1)
    setCode(newCode)

    if (value && index < CODE_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus()
    }
  }

  function handleKeyDown(index: number, e: React.KeyboardEvent) {
    if (e.key === 'Backspace' && !code[index] && index > 0) {
      inputRefs.current[index - 1]?.focus()
    }
  }

  function handlePaste(e: React.ClipboardEvent) {
    e.preventDefault()
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, CODE_LENGTH)
    if (!pasted) return

    const newCode = [...code]
    for (let i = 0; i < pasted.length; i++) {
      newCode[i] = pasted[i] ?? ''
    }
    setCode(newCode)

    const nextIndex = Math.min(pasted.length, CODE_LENGTH - 1)
    inputRefs.current[nextIndex]?.focus()
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    const fullCode = code.join('')
    if (fullCode.length !== CODE_LENGTH) {
      setError('Please enter the complete 6-digit code')
      return
    }

    if (!token) {
      setError('Missing verification token. Please use the link from your email.')
      return
    }

    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/verification/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, code: fullCode }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: 'Verification failed' }))
        throw new Error(data.detail || 'Verification failed')
      }

      setSuccess(true)
      setTimeout(() => {
        navigate('/', { replace: true })
      }, 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed')
    } finally {
      setLoading(false)
    }
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
            background: success ? 'var(--color-success)' : 'var(--color-primary)',
            color: 'var(--color-primary-foreground)',
            transition: 'background 0.3s',
          }}
        >
          {success ? (
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 6 9 17l-5-5" />
            </svg>
          ) : (
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          )}
        </div>

        <div className="space-y-2">
          <h1 className="text-2xl font-semibold" style={{ fontFamily: 'var(--font-heading)' }}>
            {success ? 'Email verified!' : 'Enter verification code'}
          </h1>
          {success ? (
            <p className="text-sm text-muted-foreground">
              Your email has been verified. Redirecting...
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              Enter the 6-digit code from the email we sent you.
            </p>
          )}
        </div>

        {error && (
          <div role="alert" className="rounded-lg border border-destructive bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {!success && (
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="flex justify-center gap-3" onPaste={handlePaste}>
              {code.map((digit, index) => (
                <input
                  key={index}
                  ref={(el) => { inputRefs.current[index] = el }}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleChange(index, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(index, e)}
                  disabled={loading}
                  className="w-12 h-14 text-center text-2xl font-bold rounded-lg border border-border bg-background text-foreground focus:border-primary focus:ring-2 focus:ring-primary/20 outline-none transition-all disabled:opacity-50"
                  aria-label={`Digit ${index + 1}`}
                />
              ))}
            </div>

            <button
              type="submit"
              disabled={loading || code.join('').length !== CODE_LENGTH}
              className="inline-flex w-full items-center justify-center rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {loading ? 'Verifying...' : 'Verify email'}
            </button>
          </form>
        )}

        {!success && (
          <p className="text-xs text-muted-foreground">
            Didn't receive a code?{' '}
            <a href="/check-email" className="text-primary hover:underline">
              Resend verification email
            </a>
          </p>
        )}
      </div>
    </div>
  )
}
