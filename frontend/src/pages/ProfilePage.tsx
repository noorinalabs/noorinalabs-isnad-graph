import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchProfile,
  updateProfile,
  fetchSessions,
  revokeSession,
} from '../api/profile-client'
import type { UserPreferences } from '../api/profile-client'

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

function roleBadgeColor(role: string | null): string {
  switch (role) {
    case 'admin':
      return 'var(--color-destructive, #ef4444)'
    case 'moderator':
      return 'var(--color-warning, #f59e0b)'
    case 'editor':
      return 'var(--color-primary)'
    default:
      return 'var(--color-muted-foreground)'
  }
}

export default function ProfilePage() {
  const queryClient = useQueryClient()
  const [editingName, setEditingName] = useState(false)
  const [nameInput, setNameInput] = useState('')

  const { data: profile, isLoading, error } = useQuery({
    queryKey: ['profile'],
    queryFn: fetchProfile,
  })

  const { data: sessions } = useQuery({
    queryKey: ['sessions'],
    queryFn: fetchSessions,
  })

  const updateNameMutation = useMutation({
    mutationFn: (displayName: string) => updateProfile({ display_name: displayName }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profile'] })
      setEditingName(false)
    },
  })

  const updatePrefsMutation = useMutation({
    mutationFn: (preferences: UserPreferences) => updateProfile({ preferences }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['profile'] }),
  })

  const revokeSessionMutation = useMutation({
    mutationFn: (sessionId: string) => revokeSession(sessionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  })

  if (isLoading) return <p>Loading profile...</p>
  if (error) return <p className="error-text">Error: {(error as Error).message}</p>
  if (!profile) return null

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
                <span style={valueStyle}>{profile.name}</span>
                <button
                  className="btn"
                  onClick={() => {
                    setNameInput(profile.name)
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
            <div style={valueStyle}>{profile.email}</div>
          </div>
          <div>
            <div style={labelStyle}>Auth Provider</div>
            <div style={valueStyle}>{providerLabel(profile.provider)}</div>
          </div>
          <div>
            <div style={labelStyle}>Member Since</div>
            <div style={valueStyle}>
              {new Date(profile.created_at).toLocaleDateString()}
            </div>
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
                color: '#fff',
                background: roleBadgeColor(profile.role),
              }}
            >
              {(profile.role ?? 'viewer').toUpperCase()}
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
              value={profile.preferences.default_search_mode}
              onChange={(e) =>
                updatePrefsMutation.mutate({
                  ...profile.preferences,
                  default_search_mode: e.target.value,
                })
              }
            >
              <option value="fulltext">Full Text</option>
              <option value="semantic">Semantic</option>
            </select>
          </div>
          <div>
            <div style={labelStyle}>Results Per Page</div>
            <select
              className="form-input"
              value={profile.preferences.results_per_page}
              onChange={(e) =>
                updatePrefsMutation.mutate({
                  ...profile.preferences,
                  results_per_page: Number(e.target.value),
                })
              }
            >
              {[10, 20, 50, 100].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
          <div>
            <div style={labelStyle}>Language (stub)</div>
            <select
              className="form-input"
              value={profile.preferences.language_preference}
              onChange={(e) =>
                updatePrefsMutation.mutate({
                  ...profile.preferences,
                  language_preference: e.target.value,
                })
              }
            >
              <option value="en">English</option>
              <option value="ar">Arabic</option>
            </select>
          </div>
          <div>
            <div style={labelStyle}>Theme (stub)</div>
            <select
              className="form-input"
              value={profile.preferences.theme_preference}
              onChange={(e) =>
                updatePrefsMutation.mutate({
                  ...profile.preferences,
                  theme_preference: e.target.value,
                })
              }
            >
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </div>
        </div>
        {updatePrefsMutation.isPending && (
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
                      disabled={revokeSessionMutation.isPending}
                    >
                      Revoke
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
