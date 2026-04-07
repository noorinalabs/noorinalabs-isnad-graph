import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useTheme } from '../hooks/useTheme'

function providerLabel(provider: string): string {
  switch (provider) {
    case 'google':
      return 'Google'
    case 'github':
      return 'GitHub'
    default:
      return provider.charAt(0).toUpperCase() + provider.slice(1)
  }
}

export default function UserMenu() {
  const { user, logout, signOutAll, role } = useAuth()
  const { resolvedTheme, toggle } = useTheme()
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  // Close on outside click
  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open])

  if (!user) return null

  const initials = user.name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  return (
    <div ref={menuRef} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen((prev) => !prev)}
        aria-label="User menu"
        aria-expanded={open}
        aria-haspopup="true"
        style={{
          width: 32,
          height: 32,
          borderRadius: '50%',
          border: 'var(--border-width-thin) solid var(--color-border)',
          background: 'var(--color-accent)',
          color: 'var(--color-primary)',
          fontFamily: 'var(--font-heading)',
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {initials}
      </button>

      {open && (
        <div
          role="menu"
          style={{
            position: 'absolute',
            top: 'calc(100% + var(--spacing-2))',
            right: 0,
            minWidth: 240,
            background: 'var(--color-card)',
            border: 'var(--border-width-thin) solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-lg)',
            zIndex: 50,
            overflow: 'hidden',
          }}
        >
          {/* User info section */}
          <div
            style={{
              padding: 'var(--spacing-4)',
              borderBottom: 'var(--border-width-thin) solid var(--color-border)',
            }}
          >
            <div
              style={{
                fontFamily: 'var(--font-heading)',
                fontSize: 'var(--text-sm)',
                fontWeight: 600,
                color: 'var(--color-foreground)',
              }}
            >
              {user.name}
            </div>
            <div
              style={{
                fontSize: 'var(--text-xs)',
                color: 'var(--color-muted-foreground)',
                marginTop: 'var(--spacing-0_5)',
              }}
            >
              {user.email}
            </div>
            <div style={{ display: 'flex', gap: 'var(--spacing-2)', marginTop: 'var(--spacing-2)' }}>
              <span style={{ display: 'inline-block', padding: 'var(--spacing-0_5) var(--spacing-2)', fontSize: 'var(--text-xs)', fontWeight: 500, borderRadius: 'var(--radius-full)', background: 'var(--color-accent)', color: 'var(--color-primary)' }}>
                {providerLabel(user.provider)}
              </span>
              <span style={{ display: 'inline-block', padding: 'var(--spacing-0_5) var(--spacing-2)', fontSize: 'var(--text-xs)', fontWeight: 600, borderRadius: 'var(--radius-full)', background: 'var(--color-accent)', color: 'var(--color-primary)', textTransform: 'capitalize' }}>
                {role}
              </span>
            </div>
          </div>

          {/* My Profile */}
          <button role="menuitem" onClick={() => { setOpen(false); navigate('/profile') }} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 'var(--spacing-3)', padding: 'var(--spacing-3) var(--spacing-4)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-body)', fontSize: 'var(--text-sm)', color: 'var(--color-foreground)', textAlign: 'left', borderBottom: 'var(--border-width-thin) solid var(--color-border)' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
            My Profile
          </button>

          {/* Preferences */}
          <button role="menuitem" onClick={() => { setOpen(false); navigate('/profile') }} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 'var(--spacing-3)', padding: 'var(--spacing-3) var(--spacing-4)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-body)', fontSize: 'var(--text-sm)', color: 'var(--color-foreground)', textAlign: 'left', borderBottom: 'var(--border-width-thin) solid var(--color-border)' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>
            Preferences
          </button>

          {/* Theme toggle */}
          <button
            role="menuitem"
            onClick={() => {
              toggle()
            }}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--spacing-3)',
              padding: 'var(--spacing-3) var(--spacing-4)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontFamily: 'var(--font-body)',
              fontSize: 'var(--text-sm)',
              color: 'var(--color-foreground)',
              textAlign: 'left',
              borderBottom: 'var(--border-width-thin) solid var(--color-border)',
            }}
          >
            {resolvedTheme === 'dark' ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="5" />
                <line x1="12" y1="1" x2="12" y2="3" />
                <line x1="12" y1="21" x2="12" y2="23" />
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                <line x1="1" y1="12" x2="3" y2="12" />
                <line x1="21" y1="12" x2="23" y2="12" />
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            )}
            Switch to {resolvedTheme === 'dark' ? 'light' : 'dark'} mode
          </button>

          {/* Sign out */}
          <button
            role="menuitem"
            onClick={() => {
              setOpen(false)
              logout()
            }}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--spacing-3)',
              padding: 'var(--spacing-3) var(--spacing-4)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontFamily: 'var(--font-body)',
              fontSize: 'var(--text-sm)',
              color: 'var(--color-foreground)',
              textAlign: 'left',
              borderBottom: 'var(--border-width-thin) solid var(--color-border)',
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            Sign out
          </button>

          {/* Sign out everywhere */}
          <button
            role="menuitem"
            onClick={() => {
              setOpen(false)
              signOutAll()
            }}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--spacing-3)',
              padding: 'var(--spacing-3) var(--spacing-4)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontFamily: 'var(--font-body)',
              fontSize: 'var(--text-sm)',
              color: 'var(--color-destructive, #ef4444)',
              textAlign: 'left',
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
              <line x1="16" y1="4" x2="16" y2="8" />
              <line x1="14" y1="6" x2="18" y2="6" />
            </svg>
            Sign out everywhere
          </button>
        </div>
      )}
    </div>
  )
}
