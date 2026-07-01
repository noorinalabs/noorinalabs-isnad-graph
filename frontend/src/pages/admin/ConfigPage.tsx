import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

const API_BASE = '/api/v1/admin'

interface SystemConfig {
  rate_limit_per_minute: number
  cors_origins: string[]
  feature_flags: Record<string, boolean>
  max_search_results: number
  max_pagination_limit: number
  log_retention_days: number
}

interface ConfigAuditEntry {
  key: string
  old_value: string
  new_value: string
  changed_by: string
  changed_at: string
}

interface ConfigAuditResponse {
  entries: ConfigAuditEntry[]
  total: number
}

// A transient save-status banner. `isError` drives the styling instead of
// string-sniffing the message text, so the copy can be localized freely.
interface SaveStatus {
  text: string
  isError: boolean
}

async function fetchConfig(): Promise<SystemConfig> {
  const res = await fetch(`${API_BASE}/config`)
  if (!res.ok) throw new Error(`Failed to fetch config: ${res.status}`)
  return res.json()
}

async function updateConfig(data: Partial<SystemConfig>): Promise<SystemConfig> {
  const res = await fetch(`${API_BASE}/config`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Failed to update config')
  }
  return res.json()
}

async function fetchAuditLog(page = 1): Promise<ConfigAuditResponse> {
  const res = await fetch(`${API_BASE}/config/audit?page=${page}&limit=20`)
  if (!res.ok) throw new Error(`Failed to fetch audit log: ${res.status}`)
  return res.json()
}

export default function ConfigPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const { data: config, isLoading, error } = useQuery({
    queryKey: ['admin-config'],
    queryFn: fetchConfig,
  })

  const [auditPage, setAuditPage] = useState(1)
  const { data: auditData } = useQuery({
    queryKey: ['admin-config-audit', auditPage],
    queryFn: () => fetchAuditLog(auditPage),
  })

  const [formData, setFormData] = useState<Partial<SystemConfig>>({})
  const [newFlagKey, setNewFlagKey] = useState('')
  const [corsInput, setCorsInput] = useState('')
  const [saveStatus, setSaveStatus] = useState<SaveStatus | null>(null)

  useEffect(() => {
    if (config) {
      setFormData({
        rate_limit_per_minute: config.rate_limit_per_minute,
        max_search_results: config.max_search_results,
        max_pagination_limit: config.max_pagination_limit,
        log_retention_days: config.log_retention_days,
        cors_origins: [...config.cors_origins],
        feature_flags: { ...config.feature_flags },
      })
      setCorsInput(config.cors_origins.join(', '))
    }
  }, [config])

  const mutation = useMutation({
    mutationFn: updateConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-config'] })
      queryClient.invalidateQueries({ queryKey: ['admin-config-audit'] })
      setSaveStatus({ text: t('admin.config.savedMsg'), isError: false })
      setTimeout(() => setSaveStatus(null), 3000)
    },
    onError: (err: Error) => {
      setSaveStatus({ text: t('common.error', { message: err.message }), isError: true })
    },
  })

  const handleSave = () => {
    const update: Partial<SystemConfig> = {}
    if (formData.rate_limit_per_minute !== config?.rate_limit_per_minute) {
      update.rate_limit_per_minute = formData.rate_limit_per_minute
    }
    if (formData.max_search_results !== config?.max_search_results) {
      update.max_search_results = formData.max_search_results
    }
    if (formData.max_pagination_limit !== config?.max_pagination_limit) {
      update.max_pagination_limit = formData.max_pagination_limit
    }
    if (formData.log_retention_days !== config?.log_retention_days) {
      update.log_retention_days = formData.log_retention_days
    }
    const newOrigins = corsInput.split(',').map((s) => s.trim()).filter(Boolean)
    if (JSON.stringify(newOrigins) !== JSON.stringify(config?.cors_origins)) {
      update.cors_origins = newOrigins
    }
    if (JSON.stringify(formData.feature_flags) !== JSON.stringify(config?.feature_flags)) {
      update.feature_flags = formData.feature_flags
    }
    if (Object.keys(update).length === 0) {
      setSaveStatus({ text: t('admin.config.noChangesMsg'), isError: false })
      setTimeout(() => setSaveStatus(null), 3000)
      return
    }
    mutation.mutate(update)
  }

  const toggleFlag = (key: string) => {
    setFormData((prev) => ({
      ...prev,
      feature_flags: {
        ...prev.feature_flags,
        [key]: !prev.feature_flags?.[key],
      },
    }))
  }

  const addFlag = () => {
    const trimmed = newFlagKey.trim()
    if (!trimmed) return
    setFormData((prev) => ({
      ...prev,
      feature_flags: { ...prev.feature_flags, [trimmed]: false },
    }))
    setNewFlagKey('')
  }

  const removeFlag = (key: string) => {
    setFormData((prev) => {
      const flags = { ...prev.feature_flags }
      delete flags[key]
      return { ...prev, feature_flags: flags }
    })
  }

  if (isLoading) return <div className="admin-page">{t('admin.config.loading')}</div>
  if (error)
    return (
      <div className="admin-page error-text">
        {t('admin.config.errorLoading', { error: String(error) })}
      </div>
    )

  return (
    <div className="admin-page">
      <h1>{t('admin.config.title')}</h1>

      <section className="section-mb">
        <h2>{t('admin.config.sectionRateLimit')}</h2>
        <div className="grid-2col">
          <label>
            {t('admin.config.fieldRateLimit')}
            <input
              type="number"
              min={1}
              value={formData.rate_limit_per_minute ?? 60}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, rate_limit_per_minute: Number(e.target.value) }))
              }
              className="form-input-block"
            />
          </label>
          <label>
            {t('admin.config.fieldMaxSearchResults')}
            <input
              type="number"
              min={1}
              value={formData.max_search_results ?? 100}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, max_search_results: Number(e.target.value) }))
              }
              className="form-input-block"
            />
          </label>
          <label>
            {t('admin.config.fieldMaxPagination')}
            <input
              type="number"
              min={1}
              value={formData.max_pagination_limit ?? 100}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, max_pagination_limit: Number(e.target.value) }))
              }
              className="form-input-block"
            />
          </label>
        </div>
      </section>

      <section className="section-mb">
        <h2>{t('admin.config.sectionCors')}</h2>
        <label>
          {t('admin.config.fieldCorsOrigins')}
          <input
            type="text"
            value={corsInput}
            onChange={(e) => setCorsInput(e.target.value)}
            className="form-input-block"
          />
        </label>
      </section>

      <section className="section-mb">
        <h2>{t('admin.config.sectionLogRetention')}</h2>
        <label>
          {t('admin.config.fieldLogRetention')}
          <input
            type="number"
            min={1}
            max={365}
            value={formData.log_retention_days ?? 7}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, log_retention_days: Number(e.target.value) }))
            }
            className="form-input-block"
          />
        </label>
        <p className="muted-text">{t('admin.config.logRetentionNote')}</p>
      </section>

      <section className="section-mb">
        <h2>{t('admin.config.sectionFeatureFlags')}</h2>
        {Object.entries(formData.feature_flags ?? {}).map(([key, val]) => (
          <div key={key} className="flag-row">
            <label className="flex-row" style={{ flex: 1, gap: '0.5rem', cursor: 'pointer' }}>
              <input type="checkbox" checked={val} onChange={() => toggleFlag(key)} />
              <span>{key}</span>
            </label>
            <button onClick={() => removeFlag(key)} className="btn-danger">
              {t('admin.config.removeFlag')}
            </button>
          </div>
        ))}
        <div className="flex-row" style={{ marginTop: 8 }}>
          <input
            type="text"
            placeholder={t('admin.config.newFlagPlaceholder')}
            value={newFlagKey}
            onChange={(e) => setNewFlagKey(e.target.value)}
            className="form-input"
            style={{ flex: 1 }}
          />
          <button onClick={addFlag} className="btn">
            {t('admin.config.addFlag')}
          </button>
        </div>
      </section>

      <div style={{ marginBottom: 24 }}>
        <button
          onClick={handleSave}
          disabled={mutation.isPending}
          className="btn-primary"
        >
          {mutation.isPending ? t('admin.config.saving') : t('admin.config.saveConfig')}
        </button>
        {saveStatus && (
          <span className={saveStatus.isError ? 'save-error' : 'save-success'}>
            {saveStatus.text}
          </span>
        )}
      </div>

      <hr />

      <section>
        <h2>{t('admin.config.sectionAuditLog')}</h2>
        {auditData?.entries.length === 0 && <p>{t('admin.config.noConfigChanges')}</p>}
        <table className="data-table">
          <thead>
            <tr>
              <th className="audit-th">{t('admin.config.colKey')}</th>
              <th className="audit-th">{t('admin.config.colOldValue')}</th>
              <th className="audit-th">{t('admin.config.colNewValue')}</th>
              <th className="audit-th">{t('admin.config.colChangedBy')}</th>
              <th className="audit-th">{t('admin.config.colChangedAt')}</th>
            </tr>
          </thead>
          <tbody>
            {auditData?.entries.map((entry, i) => (
              <tr key={i}>
                <td className="audit-td">{entry.key}</td>
                <td className="cell-truncate">{entry.old_value}</td>
                <td className="cell-truncate">{entry.new_value}</td>
                <td className="audit-td">{entry.changed_by}</td>
                <td className="audit-td">{entry.changed_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {auditData && auditData.total > 20 && (
          <div className="pagination" style={{ marginTop: 12 }}>
            <button disabled={auditPage <= 1} onClick={() => setAuditPage((p) => p - 1)}>
              {t('common.previous')}
            </button>
            <span>{t('admin.config.pageN', { page: auditPage })}</span>
            <button
              disabled={auditPage * 20 >= auditData.total}
              onClick={() => setAuditPage((p) => p + 1)}
            >
              {t('common.next')}
            </button>
          </div>
        )}
      </section>
    </div>
  )
}
