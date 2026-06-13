import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useLocale } from '../i18n/useLocale'
import type { LocaleCode } from '../i18n/config'

/**
 * Language switcher for the UI chrome. A globe button opens a dropdown of the
 * supported locales (shown by their native name); selecting one switches the UI
 * language instantly — persistence and RTL `dir` flipping are handled by the i18n
 * bootstrap. Scope is UI chrome only; scholarly API data is never translated.
 */
export default function LanguageToggle() {
  const { t } = useTranslation()
  const { locale, locales, setLocale } = useLocale()
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Close on outside click.
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

  // Close on Escape.
  useEffect(() => {
    if (!open) return
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open])

  function choose(code: LocaleCode) {
    setLocale(code)
    setOpen(false)
  }

  return (
    <div ref={menuRef} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="theme-toggle"
        aria-label={t('language.select')}
        title={t('language.label')}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        {/* Globe icon — matches the inline-SVG style of ThemeToggle. */}
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="2" y1="12" x2="22" y2="12" />
          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          aria-label={t('language.label')}
          style={{
            position: 'absolute',
            top: 'calc(100% + var(--spacing-2))',
            insetInlineEnd: 0,
            minWidth: 180,
            background: 'var(--color-card)',
            border: 'var(--border-width-thin) solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-lg)',
            zIndex: 50,
            overflow: 'hidden',
            padding: 'var(--spacing-1)',
          }}
        >
          {locales.map((l) => {
            const active = l.code === locale
            return (
              <button
                key={l.code}
                role="menuitemradio"
                aria-checked={active}
                lang={l.code}
                dir={l.dir}
                onClick={() => choose(l.code)}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 'var(--spacing-3)',
                  padding: 'var(--spacing-2) var(--spacing-3)',
                  background: active ? 'var(--color-accent)' : 'none',
                  border: 'none',
                  borderRadius: 'var(--radius-md)',
                  cursor: 'pointer',
                  fontFamily: 'var(--font-body)',
                  fontSize: 'var(--text-sm)',
                  fontWeight: active ? 600 : 400,
                  color: active ? 'var(--color-primary)' : 'var(--color-foreground)',
                  textAlign: 'start',
                }}
              >
                {l.nativeName}
                {active && (
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
