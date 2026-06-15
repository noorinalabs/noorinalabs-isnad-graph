import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import {
  fetchProfile,
  fetchSessions,
  replacePreferences,
  revokeSession,
  updateDisplayName,
} from '../api/profile-client'
import type { UserPreferences } from '../api/profile-client'
import { useAuth } from '../hooks/useAuth'
import { useTheme } from '../hooks/useTheme'
import { useLocale } from '../i18n/useLocale'
import type { LocaleCode } from '../i18n/config'

function providerLabel(provider: string): string {
  switch (provider) {
    case 'google':
      return 'Google'
    case 'github':
      return 'GitHub'
    case 'apple':
      return 'Apple'
    case 'facebook':
      return 'Facebook'
    default:
      return provider.charAt(0).toUpperCase() + provider.slice(1)
  }
}

function roleBadgeColor(role: string): string {
  switch (role) {
    case 'admin':
      return 'var(--color-destructive)'
    case 'researcher':
      return 'var(--color-warning)'
    case 'reader':
      return 'var(--color-primary)'
    default:
      return 'var(--color-muted-foreground)'
  }
}

export default function ProfilePage() {
  const queryClient = useQueryClient()
  const { user, role, refreshUser } = useAuth()
  // The live theme + locale are the single source of truth for the controls
  // below; on login they are hydrated from the server (see PreferencesSync), and
  // a change here drives the app immediately as well as persisting (#1013/#1044).
  const { theme, setTheme } = useTheme()
  const { locale, locales, setLocale } = useLocale()
  const [editingName, setEditingName] = useState(false)
  const [nameInput, setNameInput] = useState('')

  // The profile query carries the full preferences blob — needed for a
  // read-modify-write PUT and for the non-theme/locale prefs (search mode,
  // results per page). Account info (name/email/role/...) comes from the auth
  // user, not this endpoint, which returns only `{ user_id, preferences }`.
  const { data: profile } = useQuery({
    queryKey: ['profile'],
    queryFn: fetchProfile,
  })

  const { data: sessions } = useQuery({
    queryKey: ['sessions'],
    queryFn: fetchSessions,
  })

  const prefs: UserPreferences = profile?.preferences ?? {}

  const updateNameMutation = useMutation({
    mutationFn: (displayName: string) => updateDisplayName(displayName),
    onSuccess: async () => {
      await refreshUser()
      setEditingName(false)
    },
  })

  const replacePrefsMutation = useMutation({
    mutationFn: (preferences: UserPreferences) => replacePreferences(preferences),
    onSuccess: (data) => queryClient.setQueryData(['profile'], data),
  })

  const revokeSessionMutation = useMutation({
    mutationFn: (sessionId: string) => revokeSession(sessionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  })

  // Read-modify-write: PUT replaces the whole blob, so spread the current prefs
  // and overlay the changed key(s) to avoid dropping the others.
  function persistPrefs(patch: Partial<UserPreferences>) {
    replacePrefsMutation.mutate({ ...prefs, ...patch })
  }

  function handleThemeChange(value: string) {
    const next = value as 'light' | 'dark' | 'system'
    setTheme(next)
    persistPrefs({ theme: next })
  }

  function handleLanguageChange(value: string) {
    setLocale(value as LocaleCode)
    persistPrefs({ language: value })
  }

  if (!user) return null

  const sectionStyle: React.CSSProperties = {
    marginBottom: 'var(--spacing-6)',
    padding: 'var(--spacing-5)',
    background: 'var(--color-card)',
    border: 'var(--border-width-thin) solid var(--color-border)',
    borderRadius: 'var(--radius-lg)',
  }

  const labelStyle: React.CSSProperties = {
    fontSize: 'var(--text-xs)',
    color: 'var(--color-muted-foreground)',
    marginBottom: 'var(--spacing-1)',
  }

  const valueStyle: React.CSSProperties = {
    fontSize: 'var(--text-sm)',
    color: 'var(--color-foreground)',
    fontWeight: 500,
  }

  const displayName = user.display_name ?? user.email

  return (
    <div style={{ maxWidth: 720 }}>
      <h2 style={{ fontFamily: 'var(--font-heading)', marginBottom: 'var(--spacing-6)' }}>
        My Profile
      </h2>

      {/* Account Info */}
      <div style={sectionStyle}>
        <h3
          style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'var(--text-base)',
            marginBottom: 'var(--spacing-4)',
          }}
        >
          Account Information
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-4)' }}>
          <div>
            <div style={labelStyle}>Display Name</div>
            {editingName ? (
              <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                <input
                  type="text"
                  className="form-input"
                  value={nameInput}
                  onChange={(e) => setNameInput(e.target.value)}
                  style={{ flex: 1 }}
                />
                <button
                  className="btn"
                  onClick={() => updateNameMutation.mutate(nameInput)}
                  disabled={updateNameMutation.isPending}
                >
                  Save
                </button>
                <button className="btn" onClick={() => setEditingName(false)}>
                  Cancel
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                <span style={valueStyle}>{displayName}</span>
                <button
                  className="btn"
                  onClick={() => {
                    setNameInput(user.display_name ?? '')
                    setEditingName(true)
                  }}
                  style={{ fontSize: 'var(--text-xs)', padding: 'var(--spacing-0_5) var(--spacing-2)' }}
                >
                  Edit
                </button>
              </div>
            )}
          </div>
          <div>
            <div style={labelStyle}>Email</div>
            <div style={valueStyle}>{user.email}</div>
          </div>
          <div>
            <div style={labelStyle}>Auth Provider</div>
            <div style={valueStyle}>{user.provider ? providerLabel(user.provider) : '—'}</div>
          </div>
          <div>
            <div style={labelStyle}>Member Since</div>
            <div style={valueStyle}>{new Date(user.created_at).toLocaleDateString()}</div>
          </div>
          <div>
            <div style={labelStyle}>Role</div>
            <span
              style={{
                display: 'inline-block',
                padding: 'var(--spacing-0_5) var(--spacing-2)',
                fontSize: 'var(--text-xs)',
                fontWeight: 600,
                borderRadius: 'var(--radius-full)',
                color: 'var(--color-primary-foreground)',
                background: roleBadgeColor(role),
              }}
            >
              {role.toUpperCase()}
            </span>
          </div>
        </div>
      </div>

      {/* Preferences */}
      <div style={sectionStyle}>
        <h3
          style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'var(--text-base)',
            marginBottom: 'var(--spacing-4)',
          }}
        >
          Preferences
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-4)' }}>
          <div>
            <div style={labelStyle}>Default Search Mode</div>
            <select
              className="form-input"
              value={prefs.default_search_mode ?? 'fulltext'}
              onChange={(e) => persistPrefs({ default_search_mode: e.target.value })}
            >
              <option value="fulltext">Full Text</option>
              <option value="semantic">Semantic</option>
            </select>
          </div>
          <div>
            <div style={labelStyle}>Results Per Page</div>
            <select
              className="form-input"
              value={prefs.results_per_page ?? 20}
              onChange={(e) => persistPrefs({ results_per_page: Number(e.target.value) })}
            >
              {[10, 20, 50, 100].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
          <div>
            <div style={labelStyle}>Language</div>
            <select
              className="form-input"
              value={locale}
              onChange={(e) => handleLanguageChange(e.target.value)}
            >
              {locales.map((l) => (
                <option key={l.code} value={l.code} lang={l.code}>
                  {l.nativeName}
                </option>
              ))}
            </select>
          </div>
          <div>
            <div style={labelStyle}>Theme</div>
            <select
              className="form-input"
              value={theme}
              onChange={(e) => handleThemeChange(e.target.value)}
            >
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </div>
        </div>
        {replacePrefsMutation.isPending && (
          <p style={{ marginTop: 'var(--spacing-2)', fontSize: 'var(--text-xs)' }}>Saving...</p>
        )}
      </div>

      {/* Active Sessions */}
      <div style={sectionStyle}>
        <h3
          style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'var(--text-base)',
            marginBottom: 'var(--spacing-4)',
          }}
        >
          Active Sessions
        </h3>
        {sessions && sessions.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Created</th>
                <th>Last Active</th>
                <th>IP Address</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id}>
                  <td>{new Date(s.created_at).toLocaleString()}</td>
                  <td>{new Date(s.last_active).toLocaleString()}</td>
                  <td>{s.ip_address ?? '-'}</td>
                  <td>
                    <button
                      className="btn-action btn-action-suspend"
                      onClick={() => revokeSessionMutation.mutate(s.id)}
                      disabled={revokeSessionMutation.isPending || s.is_current}
                    >
                      {s.is_current ? 'Current' : 'Revoke'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted-foreground)' }}>
            No active sessions found.
          </p>
        )}
      </div>
    </div>
  )
}
