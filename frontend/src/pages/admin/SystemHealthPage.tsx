import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { fetchSystemHealth } from '../../api/admin-client'
import styles from './SystemHealthPage.module.css'

function StatusCard({ label, ok }: { label: string; ok: boolean }) {
  const { t } = useTranslation()
  return (
    <div className={styles.card}>
      <div className={styles.cardLabel}>{label}</div>
      <div className={ok ? styles.cardValueOk : styles.cardValueDown}>
        {ok ? t('admin.systemHealth.statusConnected') : t('admin.systemHealth.statusDown')}
      </div>
    </div>
  )
}

export default function SystemHealthPage() {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-health'],
    queryFn: fetchSystemHealth,
    refetchInterval: 30_000,
  })

  return (
    <div>
      <h2>{t('admin.systemHealth.title')}</h2>

      {isLoading && <p>{t('admin.common.loading')}</p>}
      {error && (
        <p className={styles.errorText}>
          {t('common.error', { message: (error as Error).message })}
        </p>
      )}

      {data && (
        <>
          <div className={styles.cardGrid}>
            <div className={styles.card}>
              <div className={styles.cardLabel}>{t('admin.systemHealth.overallStatus')}</div>
              <div className={data.status === 'ok' ? styles.cardValueOk : styles.cardValueWarning}>
                {data.status.toUpperCase()}
              </div>
            </div>
            <StatusCard label="Neo4j" ok={data.neo4j} />
            <StatusCard label="PostgreSQL" ok={data.postgres} />
            <StatusCard label="Redis" ok={data.redis} />
          </div>

          <p className={styles.refreshNote}>{t('admin.systemHealth.refreshNote')}</p>
        </>
      )}
    </div>
  )
}
