import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchHadiths } from '../api/client'

export default function ComparativePage() {
  const [page, setPage] = useState(1)
  const navigate = useNavigate()

  const { data, isLoading, error } = useQuery({
    queryKey: ['hadiths-with-parallels', page],
    queryFn: () => fetchHadiths(page, 20),
  })

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0

  return (
    <div>
      <h2>Comparative Analysis</h2>
      <p style={{ color: '#666', marginBottom: '1rem' }}>
        Browse hadiths that have cross-sectarian parallels (PARALLEL_OF relationships).
      </p>

      {isLoading && <p>Loading...</p>}
      {error && <p style={{ color: 'red' }}>Error: {(error as Error).message}</p>}

      {data && (
        <>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #ddd', textAlign: 'left' }}>
                <th style={{ padding: '0.5rem' }}>ID</th>
                <th style={{ padding: '0.5rem' }}>Source Corpus</th>
                <th style={{ padding: '0.5rem' }}>Grade</th>
                <th style={{ padding: '0.5rem' }}>Sunni Parallel</th>
                <th style={{ padding: '0.5rem' }}>Shia Parallel</th>
              </tr>
            </thead>
            <tbody>
              {data.items
                .filter((h) => h.has_sunni_parallel || h.has_shia_parallel)
                .map((h) => (
                  <tr
                    key={h.id}
                    onClick={() => navigate(`/hadiths/${h.id}`)}
                    style={{ borderBottom: '1px solid #eee', cursor: 'pointer' }}
                  >
                    <td style={{ padding: '0.5rem' }}>{h.id}</td>
                    <td style={{ padding: '0.5rem' }}>{h.source_corpus}</td>
                    <td style={{ padding: '0.5rem' }}>{h.grade_composite ?? '-'}</td>
                    <td style={{ padding: '0.5rem' }}>{h.has_sunni_parallel ? 'Yes' : 'No'}</td>
                    <td style={{ padding: '0.5rem' }}>{h.has_shia_parallel ? 'Yes' : 'No'}</td>
                  </tr>
                ))}
            </tbody>
          </table>

          <div
            style={{ marginTop: '1.5rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}
          >
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span>
              Page {data.page} of {totalPages}
            </span>
            <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Next
            </button>
          </div>
        </>
      )}
    </div>
  )
}
