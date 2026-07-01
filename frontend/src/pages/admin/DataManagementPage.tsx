import { useState } from 'react'
import { useTranslation } from 'react-i18next'
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
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-data-overview'],
    queryFn: fetchDataOverview,
  })

  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}>{t('admin.dataManagement.sectionGraphInventory')}</h3>

      {isLoading && <p>{t('admin.common.loading')}</p>}
      {error && (
        <p className={styles.errorText}>
          {t('common.error', { message: (error as Error).message })}
        </p>
      )}

      {data && (
        <>
          <div className={styles.cardGrid}>
            <StatCard label={t('admin.dataManagement.statTotalNodes')} value={data.total_nodes.toLocaleString()} />
            <StatCard label={t('admin.dataManagement.statTotalRelationships')} value={data.total_relationships.toLocaleString()} />
          </div>

          <h4 className={styles.sectionTitle}>{t('admin.dataManagement.nodesByLabel')}</h4>
          {data.node_counts.length === 0 ? (
            <p className={styles.emptyText}>{t('admin.dataManagement.noNodes')}</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t('admin.dataManagement.colLabel')}</th>
                  <th>{t('admin.common.colCount')}</th>
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

          <h4 className={styles.sectionTitle}>{t('admin.dataManagement.relationshipsByType')}</h4>
          {data.relationship_counts.length === 0 ? (
            <p className={styles.emptyText}>{t('admin.dataManagement.noRelationships')}</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t('admin.dataManagement.colType')}</th>
                  <th>{t('admin.common.colCount')}</th>
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
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-data-sources'],
    queryFn: fetchDataSources,
  })

  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}>{t('admin.dataManagement.sectionProvenance')}</h3>

      {isLoading && <p>{t('admin.common.loading')}</p>}
      {error && (
        <p className={styles.errorText}>
          {t('common.error', { message: (error as Error).message })}
        </p>
      )}

      {data && (
        <>
          <div className={styles.cardGrid}>
            <StatCard label={t('admin.dataManagement.statDistinctSources')} value={data.distinct_sources.toLocaleString()} />
            <StatCard label={t('admin.dataManagement.statHadiths')} value={data.total_hadiths.toLocaleString()} />
            <StatCard label={t('admin.dataManagement.statCollections')} value={data.total_collections.toLocaleString()} />
          </div>

          {data.sources.length === 0 ? (
            <p className={styles.emptyText}>{t('admin.dataManagement.noSourceContent')}</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t('admin.dataManagement.colSourceCorpus')}</th>
                  <th>{t('admin.dataManagement.colHadiths')}</th>
                  <th>{t('admin.dataManagement.colCollections')}</th>
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
  const { t } = useTranslation()
  const heading = result.deleted
    ? t('admin.dataManagement.purgeComplete')
    : t('admin.dataManagement.purgeDryRun')
  const nodes = t('admin.dataManagement.purgeNodes', { count: result.total_nodes })
  const relationships = t('admin.dataManagement.purgeRelationships', {
    count: result.total_relationships,
  })
  return (
    <div role="status" className={styles.purgeResult}>
      <p>
        <strong>{heading}</strong>
        {' — '}
        {t('admin.dataManagement.purgeSourceCorpus')} <code>{result.source_corpus}</code>
      </p>
      <p>
        {result.deleted
          ? t('admin.dataManagement.purgeRemoved', { nodes, relationships })
          : t('admin.dataManagement.purgeWouldRemove', { nodes, relationships })}
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
  const { t } = useTranslation()
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
      <h3 className={styles.sectionTitle}>{t('admin.dataManagement.dangerZoneTitle')}</h3>
      <p className={styles.emptyText}>{t('admin.dataManagement.dangerZoneDesc')}</p>

      <div className={styles.purgeControls}>
        <label htmlFor="purge-source-select">{t('admin.dataManagement.labelSourceCorpus')}</label>
        <select
          id="purge-source-select"
          value={selected}
          onChange={(e) => onSelect(e.target.value)}
        >
          <option value="">{t('admin.dataManagement.selectSourcePlaceholder')}</option>
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
          {previewMutation.isPending
            ? t('admin.dataManagement.previewing')
            : t('admin.dataManagement.previewRemoval')}
        </button>
      </div>

      {error && (
        <p role="alert" className={styles.errorText}>
          {t('common.error', { message: (error as Error).message })}
        </p>
      )}

      {preview && !preview.deleted && <PurgeResultPanel result={preview} />}

      {preview && !preview.deleted && (
        <div className={styles.purgeControls}>
          <label htmlFor="purge-confirm-input">
            {t('admin.dataManagement.confirmTypePre')}
            <code>{selected}</code>
            {t('admin.dataManagement.confirmTypePost')}
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
            {purgeMutation.isPending
              ? t('admin.dataManagement.purging')
              : t('admin.dataManagement.purgeButton')}
          </button>
        </div>
      )}

      {purgeMutation.data?.deleted && <PurgeResultPanel result={purgeMutation.data} />}
    </section>
  )
}

export default function DataManagementPage() {
  const { t } = useTranslation()
  return (
    <div>
      <h2>{t('admin.dataManagement.title')}</h2>
      <p className={styles.emptyText}>{t('admin.dataManagement.subtitle')}</p>
      <OverviewSection />
      <SourcesSection />
      <PurgeSection />
    </div>
  )
}
