import { useQuery } from '@tanstack/react-query'
import { fetchDataOverview, fetchDataSources } from '../../api/admin-client'
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

export default function DataManagementPage() {
  return (
    <div>
      <h2>Data Management</h2>
      <p className={styles.emptyText}>
        Read-only overview of loaded graph data and its provenance.
      </p>
      <OverviewSection />
      <SourcesSection />
    </div>
  )
}
