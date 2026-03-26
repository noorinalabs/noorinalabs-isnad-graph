import { useQuery } from '@tanstack/react-query'
import { fetchSystemHealth } from '../../api/admin-client'
import styles from './SystemHealthPage.module.css'

function StatusCard({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className={styles.card}>
      <div className={styles.cardLabel}>{label}</div>
      <div className={ok ? styles.cardValueOk : styles.cardValueDown}>
        {ok ? 'Connected' : 'Down'}
      </div>
    </div>
  )
}

export default function SystemHealthPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-health'],
    queryFn: fetchSystemHealth,
    refetchInterval: 30_000,
  })

  return (
    <div>
      <h2>System Health</h2>

      {isLoading && <p>Loading...</p>}
      {error && <p className={styles.errorText}>Error: {(error as Error).message}</p>}

      {data && (
        <>
          <div className={styles.cardGrid}>
            <div className={styles.card}>
              <div className={styles.cardLabel}>Overall Status</div>
              <div className={data.status === 'ok' ? styles.cardValueOk : styles.cardValueWarning}>
                {data.status.toUpperCase()}
              </div>
            </div>
            <StatusCard label="Neo4j" ok={data.neo4j} />
            <StatusCard label="PostgreSQL" ok={data.postgres} />
            <StatusCard label="Redis" ok={data.redis} />
          </div>

          <p className={styles.refreshNote}>Auto-refreshes every 30 seconds.</p>
        </>
      )}
    </div>
  )
}
