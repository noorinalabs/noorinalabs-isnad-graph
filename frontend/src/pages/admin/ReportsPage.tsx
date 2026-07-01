import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { fetchSystemReports } from '../../api/client'
import type { SystemReport } from '../../types/api'

function MetricCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="metric-card">
      <h3>{title}</h3>
      {children}
    </div>
  )
}

function StatRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="stat-row">
      <span>{label}</span>
      <strong>{typeof value === 'number' ? value.toLocaleString() : value}</strong>
    </div>
  )
}

export default function ReportsPage() {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery<SystemReport>({
    queryKey: ['system-reports'],
    queryFn: fetchSystemReports,
  })

  if (isLoading) return <p>{t('admin.reports.loading')}</p>
  if (error)
    return <p className="error-text">{t('common.error', { message: (error as Error).message })}</p>
  if (!data) return <p>{t('admin.reports.noReportData')}</p>

  return (
    <div>
      <h2>{t('admin.reports.title')}</h2>

      {data.pipeline && (
        <MetricCard title={t('admin.reports.cardPipeline')}>
          <StatRow label={t('admin.reports.rowTotalStagingFiles')} value={data.pipeline.total_files} />
          <StatRow label={t('admin.reports.rowTotalRows')} value={data.pipeline.total_rows} />
          {data.pipeline.files.length > 0 && (
            <details style={{ marginTop: '0.5rem' }}>
              <summary style={{ cursor: 'pointer' }}>
                {t('admin.reports.fileDetails', { count: data.pipeline.files.length })}
              </summary>
              <table
                className="data-table data-table-compact"
                style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}
              >
                <thead>
                  <tr>
                    <th>{t('admin.reports.colFile')}</th>
                    <th>{t('admin.reports.colRows')}</th>
                    <th>{t('admin.reports.colColumns')}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.pipeline.files.map((f: Record<string, unknown>, i: number) => (
                    <tr key={i}>
                      <td className="mono">{String(f.file ?? '')}</td>
                      <td>{Number(f.rows ?? 0).toLocaleString()}</td>
                      <td>{String(f.columns ?? '')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          )}
        </MetricCard>
      )}

      {data.disambiguation && (
        <MetricCard title={t('admin.reports.cardDisambiguation')}>
          <StatRow label={t('admin.reports.rowNerMentions')} value={data.disambiguation.ner_mention_count} />
          <StatRow label={t('admin.reports.rowCanonicalNarrators')} value={data.disambiguation.canonical_narrator_count} />
          <StatRow label={t('admin.reports.rowAmbiguousMentions')} value={data.disambiguation.ambiguous_count} />
          <StatRow label={t('admin.reports.rowResolutionRate')} value={`${data.disambiguation.resolution_rate_pct}%`} />
          <StatRow label={t('admin.reports.rowAmbiguousRate')} value={`${data.disambiguation.ambiguous_pct}%`} />
        </MetricCard>
      )}

      {data.dedup && (
        <MetricCard title={t('admin.reports.cardDedup')}>
          <StatRow label={t('admin.reports.rowParallelLinks')} value={data.dedup.parallel_links_count} />
          <StatRow label={t('admin.reports.rowVerbatim')} value={data.dedup.parallel_verbatim} />
          <StatRow label={t('admin.reports.rowCloseParaphrase')} value={data.dedup.parallel_close_paraphrase} />
          <StatRow label={t('admin.reports.rowThematic')} value={data.dedup.parallel_thematic} />
          <StatRow label={t('admin.reports.rowCrossSect')} value={data.dedup.parallel_cross_sect} />
        </MetricCard>
      )}

      {data.graph_validation && (
        <MetricCard title={t('admin.reports.cardGraphValidation')}>
          <StatRow label={t('admin.reports.rowOrphanNarrators')} value={data.graph_validation.orphan_narrators} />
          <StatRow label={t('admin.reports.rowOrphanHadiths')} value={data.graph_validation.orphan_hadiths} />
          <StatRow label={t('admin.reports.rowChainIntegrity')} value={`${data.graph_validation.chain_integrity_pct}%`} />
          <StatRow
            label={t('admin.reports.rowCollectionCoverage')}
            value={`${data.graph_validation.collection_coverage_pct}%`}
          />
        </MetricCard>
      )}

      {data.topic_coverage && (
        <MetricCard title={t('admin.reports.cardTopicClassification')}>
          <StatRow label={t('admin.reports.rowTotalHadiths')} value={data.topic_coverage.total_hadiths} />
          <StatRow label={t('admin.reports.rowClassified')} value={data.topic_coverage.classified_count} />
          <StatRow label={t('admin.reports.rowCoverage')} value={`${data.topic_coverage.coverage_pct}%`} />
        </MetricCard>
      )}

      {!data.pipeline &&
        !data.disambiguation &&
        !data.dedup &&
        !data.graph_validation &&
        !data.topic_coverage && <p>{t('admin.reports.noReportDataRun')}</p>}
    </div>
  )
}
