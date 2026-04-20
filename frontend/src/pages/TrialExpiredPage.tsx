import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function TrialExpiredPage() {
  const { user, signOut } = useAuth()

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: 'var(--color-background)',
        padding: 'var(--spacing-6)',
      }}
    >
      <div
        style={{
          maxWidth: 520,
          width: '100%',
          textAlign: 'center',
          padding: 'var(--spacing-10)',
          background: 'var(--color-card)',
          border: 'var(--border-width-thin) solid var(--color-border)',
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-xl)',
        }}
      >
        {/* Clock icon */}
        <div
          style={{
            width: 64,
            height: 64,
            borderRadius: '50%',
            background: 'var(--color-destructive)',
            color: 'white',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto var(--spacing-6)',
          }}
        >
          <svg
            width="32"
            height="32"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
        </div>

        <h1
          style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'var(--text-2xl)',
            fontWeight: 700,
            color: 'var(--color-foreground)',
            marginBottom: 'var(--spacing-3)',
          }}
        >
          Your free trial has ended
        </h1>

        <p
          style={{
            fontSize: 'var(--text-base)',
            color: 'var(--color-muted-foreground)',
            lineHeight: 1.6,
            marginBottom: 'var(--spacing-8)',
          }}
        >
          {user?.display_name ? `${user.display_name}, your` : 'Your'} 7-day free trial of Isnad Graph has
          expired. Upgrade to a paid plan to continue exploring hadith chains, narrator networks,
          and scholarly analysis tools.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
          <Link
            to="/pricing"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 'var(--spacing-3) var(--spacing-6)',
              borderRadius: 'var(--radius-md)',
              background: 'var(--color-primary)',
              color: 'var(--color-primary-foreground)',
              fontFamily: 'var(--font-body)',
              fontSize: 'var(--text-base)',
              fontWeight: 600,
              textDecoration: 'none',
              transition: 'opacity var(--duration-fast) var(--ease-default)',
            }}
          >
            View pricing plans
          </Link>

          <button
            onClick={signOut}
            style={{
              padding: 'var(--spacing-2) var(--spacing-4)',
              border: 'none',
              background: 'none',
              color: 'var(--color-muted-foreground)',
              fontFamily: 'var(--font-body)',
              fontSize: 'var(--text-sm)',
              cursor: 'pointer',
              textDecoration: 'underline',
              textUnderlineOffset: '2px',
            }}
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  )
}
