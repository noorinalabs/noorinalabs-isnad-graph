import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { fetchDashboardStats } from '../../api/admin-client'
import { useAuth } from '../../hooks/useAuth'
import { mintSsoCookie } from '../../api/sso-client'

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div
      style={{
        padding: 'var(--spacing-4)',
        background: 'var(--color-card)',
        border: 'var(--border-width-thin) solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
      }}
    >
      <div
        style={{
          fontSize: 'var(--text-xs)',
          color: 'var(--color-muted-foreground)',
          marginBottom: 'var(--spacing-1)',
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 'var(--text-2xl)',
          fontWeight: 700,
          fontFamily: 'var(--font-heading)',
          color: 'var(--color-foreground)',
        }}
      >
        {value}
      </div>
    </div>
  )
}

interface ObsLink {
  labelKey: string
  descKey: string
  href: string
}

const OBS_LINKS: ObsLink[] = [
  {
    labelKey: 'admin.dashboard.obsGrafanaLabel',
    descKey: 'admin.dashboard.obsGrafanaDesc',
    href: '/grafana/',
  },
  {
    labelKey: 'admin.dashboard.obsLogsLabel',
    descKey: 'admin.dashboard.obsLogsDesc',
    href: '/grafana/explore',
  },
  {
    labelKey: 'admin.dashboard.obsAlertsLabel',
    descKey: 'admin.dashboard.obsAlertsDesc',
    href: '/grafana/alerting/list',
  },
]

// Re-enabled with the app-session → Grafana SSO bridge (ig#1081), reversing the
// ig#1073 hide. A bare top-level navigation to `/grafana` would dead-end at
// Grafana's own login wall, so on click we first mint a short-lived parent-domain
// `nl_sso` cookie (POST /auth/sso-cookie — user-service#171) and only then
// navigate. forward_auth on the Grafana vhost validates that cookie and admin-
// gates access (noorinalabs-deploy#458). HARD CUTOVER: the live carry only works
// once user-service#171 is deployed on the target env. Admin-gated by the caller
// (DashboardPage renders this only when `isAdmin`).
export function ObservabilitySection() {
  const { t } = useTranslation()
  // Which link is currently minting (drives the disabled/busy affordance); null
  // when idle. `error` holds the inline failure copy for the most recent attempt.
  const [pendingHref, setPendingHref] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleNavigate(
    e: React.MouseEvent<HTMLAnchorElement>,
    href: string,
  ) {
    // Always intercept: a default navigation would skip the cookie mint and
    // dead-end at Grafana's login.
    e.preventDefault()
    if (pendingHref) return // a mint is already in flight
    setError(null)
    setPendingHref(href)
    try {
      // Await the mint (the browser stores the HttpOnly parent-domain cookie),
      // THEN do a top-level navigation so SameSite=Lax carries it cross-subdomain.
      await mintSsoCookie()
      window.location.assign(href)
      // On success the page is navigating away — leave `pendingHref` set so the
      // links stay inert during the unload.
    } catch (err) {
      // 401/403/network: do NOT navigate (would dead-end at Grafana's login).
      // ApiError carries a friendly, localized message; fall back for anything else.
      setError(err instanceof Error ? err.message : t('admin.dashboard.obsError'))
      setPendingHref(null)
    }
  }

  return (
    <section style={{ marginTop: 'var(--spacing-6)' }}>
      <h3
        style={{
          fontFamily: 'var(--font-heading)',
          fontSize: 'var(--text-base)',
          marginBottom: 'var(--spacing-3)',
        }}
      >
        {t('admin.dashboard.observability')}
      </h3>
      {error && (
        <p className="error-text" role="alert" style={{ marginBottom: 'var(--spacing-3)' }}>
          {error}
        </p>
      )}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 'var(--spacing-4)',
        }}
      >
        {OBS_LINKS.map(({ labelKey, descKey, href }) => {
          const label = t(labelKey)
          const description = t(descKey)
          const busy = pendingHref === href
          return (
            <a
              key={href}
              href={href}
              onClick={(e) => handleNavigate(e, href)}
              aria-busy={busy}
              aria-disabled={pendingHref !== null}
              style={{
                display: 'block',
                padding: 'var(--spacing-4)',
                background: 'var(--color-card)',
                border: 'var(--border-width-thin) solid var(--color-border)',
                borderRadius: 'var(--radius-lg)',
                textDecoration: 'none',
                color: 'var(--color-foreground)',
                opacity: pendingHref !== null && !busy ? 0.6 : 1,
                cursor: pendingHref !== null ? 'progress' : 'pointer',
              }}
            >
              <div
                style={{
                  fontSize: 'var(--text-sm)',
                  fontWeight: 600,
                  fontFamily: 'var(--font-heading)',
                  marginBottom: 'var(--spacing-1)',
                }}
              >
                {busy ? `${label}…` : label}
              </div>
              <div
                style={{
                  fontSize: 'var(--text-xs)',
                  color: 'var(--color-muted-foreground)',
                }}
              >
                {description}
              </div>
            </a>
          )
        })}
      </div>
    </section>
  )
}

export default function DashboardPage() {
  const { t } = useTranslation()
  const { isAdmin } = useAuth()
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-dashboard-stats'],
    queryFn: fetchDashboardStats,
  })

  if (isLoading) return <p>{t('admin.dashboard.loading')}</p>
  if (error)
    return <p className="error-text">{t('common.error', { message: (error as Error).message })}</p>
  if (!data) return null

  return (
    <div>
      <h2>{t('admin.dashboard.title')}</h2>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 'var(--spacing-4)',
          marginBottom: 'var(--spacing-6)',
          marginTop: 'var(--spacing-4)',
        }}
      >
        <StatCard label={t('admin.dashboard.statTotalUsers')} value={data.total_users.toLocaleString()} />
        <StatCard label={t('admin.dashboard.statActiveUsers')} value={data.active_users.toLocaleString()} />
        <StatCard label={t('admin.dashboard.statDeactivatedUsers')} value={data.deactivated_users.toLocaleString()} />
        <StatCard label={t('admin.dashboard.statNew7d')} value={data.new_registrations_7d.toLocaleString()} />
        <StatCard label={t('admin.dashboard.statActiveSessions')} value={data.active_sessions.toLocaleString()} />
      </div>

      {data.users_by_role.length > 0 && (
        <>
          <h3
            style={{
              fontFamily: 'var(--font-heading)',
              fontSize: 'var(--text-base)',
              marginBottom: 'var(--spacing-3)',
            }}
          >
            {t('admin.dashboard.usersByRole')}
          </h3>
          <table className="data-table" style={{ maxWidth: 400 }}>
            <thead>
              <tr>
                <th>{t('admin.dashboard.colRole')}</th>
                <th>{t('admin.dashboard.colCount')}</th>
              </tr>
            </thead>
            <tbody>
              {data.users_by_role.map((rc) => (
                <tr key={rc.role}>
                  <td style={{ textTransform: 'capitalize' }}>{rc.role}</td>
                  <td>{rc.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {isAdmin && <ObservabilitySection />}
    </div>
  )
}
