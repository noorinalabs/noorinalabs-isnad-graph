import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

const API_BASE = '/api/v1/admin'

interface SystemConfig {
  rate_limit_per_minute: number
  cors_origins: string[]
  feature_flags: Record<string, boolean>
  max_search_results: number
  max_pagination_limit: number
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
  const [saveMessage, setSaveMessage] = useState('')

  useEffect(() => {
    if (config) {
      setFormData({
        rate_limit_per_minute: config.rate_limit_per_minute,
        max_search_results: config.max_search_results,
        max_pagination_limit: config.max_pagination_limit,
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
      setSaveMessage('Configuration saved.')
      setTimeout(() => setSaveMessage(''), 3000)
    },
    onError: (err: Error) => {
      setSaveMessage(`Error: ${err.message}`)
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
    const newOrigins = corsInput.split(',').map((s) => s.trim()).filter(Boolean)
    if (JSON.stringify(newOrigins) !== JSON.stringify(config?.cors_origins)) {
      update.cors_origins = newOrigins
    }
    if (JSON.stringify(formData.feature_flags) !== JSON.stringify(config?.feature_flags)) {
      update.feature_flags = formData.feature_flags
    }
    if (Object.keys(update).length === 0) {
      setSaveMessage('No changes to save.')
      setTimeout(() => setSaveMessage(''), 3000)
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

  if (isLoading) return <div style={{ padding: 24 }}>Loading configuration...</div>
  if (error) return <div style={{ padding: 24, color: 'red' }}>Error loading config: {String(error)}</div>

  return (
    <div style={{ padding: 24, maxWidth: 800 }}>
      <h1>System Configuration</h1>

      <section style={{ marginBottom: 32 }}>
        <h2>Rate Limiting &amp; Pagination</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
          <label>
            Rate limit (req/min)
            <input
              type="number"
              min={1}
              value={formData.rate_limit_per_minute ?? 60}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, rate_limit_per_minute: Number(e.target.value) }))
              }
              style={{ display: 'block', width: '100%', marginTop: 4, padding: 8 }}
            />
          </label>
          <label>
            Max search results
            <input
              type="number"
              min={1}
              value={formData.max_search_results ?? 100}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, max_search_results: Number(e.target.value) }))
              }
              style={{ display: 'block', width: '100%', marginTop: 4, padding: 8 }}
            />
          </label>
          <label>
            Max pagination limit
            <input
              type="number"
              min={1}
              value={formData.max_pagination_limit ?? 100}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, max_pagination_limit: Number(e.target.value) }))
              }
              style={{ display: 'block', width: '100%', marginTop: 4, padding: 8 }}
            />
          </label>
        </div>
      </section>

      <section style={{ marginBottom: 32 }}>
        <h2>CORS Origins</h2>
        <label>
          Comma-separated origins
          <input
            type="text"
            value={corsInput}
            onChange={(e) => setCorsInput(e.target.value)}
            style={{ display: 'block', width: '100%', marginTop: 4, padding: 8 }}
          />
        </label>
      </section>

      <section style={{ marginBottom: 32 }}>
        <h2>Feature Flags</h2>
        {Object.entries(formData.feature_flags ?? {}).map(([key, val]) => (
          <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <input type="checkbox" checked={val} onChange={() => toggleFlag(key)} />
            <span style={{ flex: 1 }}>{key}</span>
            <button onClick={() => removeFlag(key)} style={{ color: 'red' }}>Remove</button>
          </div>
        ))}
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <input
            type="text"
            placeholder="New flag name"
            value={newFlagKey}
            onChange={(e) => setNewFlagKey(e.target.value)}
            style={{ flex: 1, padding: 8 }}
          />
          <button onClick={addFlag}>Add Flag</button>
        </div>
      </section>

      <div style={{ marginBottom: 24 }}>
        <button
          onClick={handleSave}
          disabled={mutation.isPending}
          style={{ padding: '8px 24px', fontWeight: 'bold' }}
        >
          {mutation.isPending ? 'Saving...' : 'Save Configuration'}
        </button>
        {saveMessage && (
          <span style={{ marginLeft: 12, color: saveMessage.startsWith('Error') ? 'red' : 'green' }}>
            {saveMessage}
          </span>
        )}
      </div>

      <hr />

      <section>
        <h2>Audit Log</h2>
        {auditData?.entries.length === 0 && <p>No config changes recorded yet.</p>}
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', padding: 8, borderBottom: '1px solid #ccc' }}>Key</th>
              <th style={{ textAlign: 'left', padding: 8, borderBottom: '1px solid #ccc' }}>Old Value</th>
              <th style={{ textAlign: 'left', padding: 8, borderBottom: '1px solid #ccc' }}>New Value</th>
              <th style={{ textAlign: 'left', padding: 8, borderBottom: '1px solid #ccc' }}>Changed By</th>
              <th style={{ textAlign: 'left', padding: 8, borderBottom: '1px solid #ccc' }}>Changed At</th>
            </tr>
          </thead>
          <tbody>
            {auditData?.entries.map((entry, i) => (
              <tr key={i}>
                <td style={{ padding: 8, borderBottom: '1px solid #eee' }}>{entry.key}</td>
                <td style={{ padding: 8, borderBottom: '1px solid #eee', maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis' }}>{entry.old_value}</td>
                <td style={{ padding: 8, borderBottom: '1px solid #eee', maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis' }}>{entry.new_value}</td>
                <td style={{ padding: 8, borderBottom: '1px solid #eee' }}>{entry.changed_by}</td>
                <td style={{ padding: 8, borderBottom: '1px solid #eee' }}>{entry.changed_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {auditData && auditData.total > 20 && (
          <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
            <button disabled={auditPage <= 1} onClick={() => setAuditPage((p) => p - 1)}>
              Previous
            </button>
            <span>Page {auditPage}</span>
            <button
              disabled={auditPage * 20 >= auditData.total}
              onClick={() => setAuditPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        )}
      </section>
    </div>
  )
}
