import { useQuery } from '@tanstack/react-query'
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
  const { data, isLoading, error } = useQuery<SystemReport>({
    queryKey: ['system-reports'],
    queryFn: fetchSystemReports,
  })

  if (isLoading) return <p>Loading reports...</p>
  if (error) return <p className="error-text">Error: {(error as Error).message}</p>
  if (!data) return <p>No report data available.</p>

  return (
    <div>
      <h2>System Reports</h2>

      {data.pipeline && (
        <MetricCard title="Pipeline Metrics">
          <StatRow label="Total staging files" value={data.pipeline.total_files} />
          <StatRow label="Total rows" value={data.pipeline.total_rows} />
          {data.pipeline.files.length > 0 && (
            <details style={{ marginTop: '0.5rem' }}>
              <summary style={{ cursor: 'pointer' }}>
                File details ({data.pipeline.files.length})
              </summary>
              <table
                className="data-table data-table-compact"
                style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}
              >
                <thead>
                  <tr>
                    <th>File</th>
                    <th>Rows</th>
                    <th>Columns</th>
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
        <MetricCard title="Disambiguation Rates">
          <StatRow label="NER mentions" value={data.disambiguation.ner_mention_count} />
          <StatRow label="Canonical narrators" value={data.disambiguation.canonical_narrator_count} />
          <StatRow label="Ambiguous mentions" value={data.disambiguation.ambiguous_count} />
          <StatRow label="Resolution rate" value={`${data.disambiguation.resolution_rate_pct}%`} />
          <StatRow label="Ambiguous rate" value={`${data.disambiguation.ambiguous_pct}%`} />
        </MetricCard>
      )}

      {data.dedup && (
        <MetricCard title="Dedup Coverage">
          <StatRow label="Parallel links" value={data.dedup.parallel_links_count} />
          <StatRow label="Verbatim" value={data.dedup.parallel_verbatim} />
          <StatRow label="Close paraphrase" value={data.dedup.parallel_close_paraphrase} />
          <StatRow label="Thematic" value={data.dedup.parallel_thematic} />
          <StatRow label="Cross-sect" value={data.dedup.parallel_cross_sect} />
        </MetricCard>
      )}

      {data.graph_validation && (
        <MetricCard title="Graph Validation">
          <StatRow label="Orphan narrators" value={data.graph_validation.orphan_narrators} />
          <StatRow label="Orphan hadiths" value={data.graph_validation.orphan_hadiths} />
          <StatRow label="Chain integrity" value={`${data.graph_validation.chain_integrity_pct}%`} />
          <StatRow
            label="Collection coverage"
            value={`${data.graph_validation.collection_coverage_pct}%`}
          />
        </MetricCard>
      )}

      {data.topic_coverage && (
        <MetricCard title="Topic Classification">
          <StatRow label="Total hadiths" value={data.topic_coverage.total_hadiths} />
          <StatRow label="Classified" value={data.topic_coverage.classified_count} />
          <StatRow label="Coverage" value={`${data.topic_coverage.coverage_pct}%`} />
        </MetricCard>
      )}

      {!data.pipeline &&
        !data.disambiguation &&
        !data.dedup &&
        !data.graph_validation &&
        !data.topic_coverage && (
          <p>No report data available. Run the pipeline to generate metrics.</p>
        )}
    </div>
  )
}
