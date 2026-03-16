import { useQuery } from '@tanstack/react-query'
import { fetchSystemHealth } from '../../api/admin-client'

function StatusCard({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div
      style={{
        border: '1px solid #ddd',
        borderRadius: '8px',
        padding: '1.5rem',
        minWidth: 180,
        textAlign: 'center',
      }}
    >
      <div style={{ fontSize: '0.875rem', color: '#666', marginBottom: '0.5rem' }}>{label}</div>
      <div
        style={{
          fontSize: '1.25rem',
          fontWeight: 700,
          color: ok ? '#188038' : '#d93025',
        }}
      >
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
      {error && <p style={{ color: 'red' }}>Error: {(error as Error).message}</p>}

      {data && (
        <>
          <div
            style={{
              display: 'flex',
              gap: '1rem',
              marginBottom: '2rem',
              flexWrap: 'wrap',
            }}
          >
            <div
              style={{
                border: '1px solid #ddd',
                borderRadius: '8px',
                padding: '1.5rem',
                minWidth: 180,
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: '0.875rem', color: '#666', marginBottom: '0.5rem' }}>
                Overall Status
              </div>
              <div
                style={{
                  fontSize: '1.25rem',
                  fontWeight: 700,
                  color: data.status === 'ok' ? '#188038' : '#e37400',
                }}
              >
                {data.status.toUpperCase()}
              </div>
            </div>
            <StatusCard label="Neo4j" ok={data.neo4j} />
            <StatusCard label="PostgreSQL" ok={data.postgres} />
            <StatusCard label="Redis" ok={data.redis} />
          </div>

          <p style={{ color: '#666', fontSize: '0.875rem' }}>Auto-refreshes every 30 seconds.</p>
        </>
      )}
    </div>
  )
}
