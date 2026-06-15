import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchDataOverview, fetchDataSources, purgeSource } from '../../api/admin-client'
import type { PurgeResult } from '../../types/admin'
import styles from './DataManagementPage.module.css'

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className={styles.card}>
      <div className={styles.cardLabel}>{label}</div>
      <div className={styles.cardValue}>{value}</div>
    </div>
  )
}

function OverviewSection() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-data-overview'],
    queryFn: fetchDataOverview,
  })

  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}>Graph Inventory</h3>

      {isLoading && <p>Loading...</p>}
      {error && <p className={styles.errorText}>Error: {(error as Error).message}</p>}

      {data && (
        <>
          <div className={styles.cardGrid}>
            <StatCard label="Total Nodes" value={data.total_nodes.toLocaleString()} />
            <StatCard label="Total Relationships" value={data.total_relationships.toLocaleString()} />
          </div>

          <h4 className={styles.sectionTitle}>Nodes by Label</h4>
          {data.node_counts.length === 0 ? (
            <p className={styles.emptyText}>No nodes loaded.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Label</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {data.node_counts.map((n) => (
                  <tr key={n.label}>
                    <td>{n.label}</td>
                    <td>{n.count.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h4 className={styles.sectionTitle}>Relationships by Type</h4>
          {data.relationship_counts.length === 0 ? (
            <p className={styles.emptyText}>No relationships loaded.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {data.relationship_counts.map((r) => (
                  <tr key={r.rel_type}>
                    <td>{r.rel_type}</td>
                    <td>{r.count.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </section>
  )
}

function SourcesSection() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-data-sources'],
    queryFn: fetchDataSources,
  })

  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}>Provenance by Source Corpus</h3>

      {isLoading && <p>Loading...</p>}
      {error && <p className={styles.errorText}>Error: {(error as Error).message}</p>}

      {data && (
        <>
          <div className={styles.cardGrid}>
            <StatCard label="Distinct Sources" value={data.distinct_sources.toLocaleString()} />
            <StatCard label="Hadiths" value={data.total_hadiths.toLocaleString()} />
            <StatCard label="Collections" value={data.total_collections.toLocaleString()} />
          </div>

          {data.sources.length === 0 ? (
            <p className={styles.emptyText}>No source-attributed content loaded.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Source Corpus</th>
                  <th>Hadiths</th>
                  <th>Collections</th>
                </tr>
              </thead>
              <tbody>
                {data.sources.map((s) => (
                  <tr key={s.source_corpus}>
                    <td>{s.source_corpus}</td>
                    <td>{s.hadith_count.toLocaleString()}</td>
                    <td>{s.collection_count.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </section>
  )
}

function PurgeResultPanel({ result }: { result: PurgeResult }) {
  const heading = result.deleted ? 'Purge complete' : 'Dry-run preview'
  return (
    <div role="status" className={styles.purgeResult}>
      <p>
        <strong>{heading}</strong> — source corpus <code>{result.source_corpus}</code>
      </p>
      <p>
        {result.deleted ? 'Removed' : 'Would remove'} {result.total_nodes.toLocaleString()} node
        {result.total_nodes === 1 ? '' : 's'} and{' '}
        {result.total_relationships.toLocaleString()} relationship
        {result.total_relationships === 1 ? '' : 's'}.
      </p>
      {result.node_counts.length > 0 && (
        <ul className={styles.purgeBreakdown}>
          {result.node_counts.map((n) => (
            <li key={n.label}>
              {n.label}: {n.count.toLocaleString()}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// Danger zone: per-source GRAPH purge (ig#989). Two-phase, mirroring the reset
// UX — a dry-run preview MUST run before the destructive control is usable, and
// the real run stays disabled until the admin types the exact corpus name. This
// is distinct from the ingest-platform pipeline reset (that wipes the staging
// store; this DETACH DELETEs loaded Neo4j nodes/edges).
function PurgeSection() {
  const queryClient = useQueryClient()
  const { data: sources } = useQuery({
    queryKey: ['admin-data-sources'],
    queryFn: fetchDataSources,
  })

  const [selected, setSelected] = useState('')
  const [confirmText, setConfirmText] = useState('')
  const [preview, setPreview] = useState<PurgeResult | null>(null)

  // Selecting a different corpus invalidates any prior preview / typed token so
  // a confirmation can never carry over onto a corpus it wasn't reviewed for.
  function onSelect(value: string) {
    setSelected(value)
    setConfirmText('')
    setPreview(null)
  }

  const previewMutation = useMutation({
    mutationFn: () => purgeSource(selected, true),
    onSuccess: (result) => setPreview(result),
  })

  const purgeMutation = useMutation({
    mutationFn: () => purgeSource(selected, false, confirmText),
    onSuccess: () => {
      // Reflect the now-removed data in the inventory + provenance panels.
      void queryClient.invalidateQueries({ queryKey: ['admin-data-overview'] })
      void queryClient.invalidateQueries({ queryKey: ['admin-data-sources'] })
      setConfirmText('')
      setPreview(null)
    },
  })

  const options = sources?.sources ?? []
  const canPurge =
    selected !== '' && preview !== null && confirmText === selected && !purgeMutation.isPending
  const error = previewMutation.error ?? purgeMutation.error

  return (
    <section className={`${styles.section} ${styles.dangerZone}`}>
      <h3 className={styles.sectionTitle}>Danger Zone — Per-source Purge</h3>
      <p className={styles.emptyText}>
        Permanently delete all graph nodes and relationships attributed to a single source
        corpus. This is irreversible. Preview first, then type the corpus name to confirm.
      </p>

      <div className={styles.purgeControls}>
        <label htmlFor="purge-source-select">Source corpus</label>
        <select
          id="purge-source-select"
          value={selected}
          onChange={(e) => onSelect(e.target.value)}
        >
          <option value="">Select a source…</option>
          {options.map((s) => (
            <option key={s.source_corpus} value={s.source_corpus}>
              {s.source_corpus}
            </option>
          ))}
        </select>

        <button
          type="button"
          disabled={selected === '' || previewMutation.isPending}
          onClick={() => previewMutation.mutate()}
        >
          {previewMutation.isPending ? 'Previewing…' : 'Preview removal'}
        </button>
      </div>

      {error && (
        <p role="alert" className={styles.errorText}>
          Error: {(error as Error).message}
        </p>
      )}

      {preview && !preview.deleted && <PurgeResultPanel result={preview} />}

      {preview && !preview.deleted && (
        <div className={styles.purgeControls}>
          <label htmlFor="purge-confirm-input">
            Type <code>{selected}</code> to confirm
          </label>
          <input
            id="purge-confirm-input"
            type="text"
            value={confirmText}
            autoComplete="off"
            onChange={(e) => setConfirmText(e.target.value)}
          />
          <button
            type="button"
            className={styles.purgeButton}
            disabled={!canPurge}
            onClick={() => purgeMutation.mutate()}
          >
            {purgeMutation.isPending ? 'Purging…' : 'Purge graph data'}
          </button>
        </div>
      )}

      {purgeMutation.data?.deleted && <PurgeResultPanel result={purgeMutation.data} />}
    </section>
  )
}

export default function DataManagementPage() {
  return (
    <div>
      <h2>Data Management</h2>
      <p className={styles.emptyText}>
        Read-only overview of loaded graph data and its provenance.
      </p>
      <OverviewSection />
      <SourcesSection />
      <PurgeSection />
    </div>
  )
}
