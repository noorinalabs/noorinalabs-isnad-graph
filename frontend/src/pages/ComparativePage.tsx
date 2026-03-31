import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchParallelPairs } from '../api/client'

export default function ComparativePage() {
  const [page, setPage] = useState(1)
  const navigate = useNavigate()

  const { data, isLoading, error } = useQuery({
    queryKey: ['parallel-pairs', page],
    queryFn: () => fetchParallelPairs(page, 20),
  })

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0

  return (
    <div>
      <h2 className="page-heading">Comparative Analysis</h2>
      <p className="muted-text" style={{ marginBottom: 'var(--spacing-4)' }}>
        Browse cross-sectarian parallel hadith pairs (PARALLEL_OF relationships).
      </p>

      {isLoading && (
        <div>
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="skeleton skeleton-row" style={{ width: `${90 - i * 5}%` }} />
          ))}
        </div>
      )}
      {error && <p className="error-text">Error: {(error as Error).message}</p>}

      {data && (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Sunni Hadith</th>
                <th>Shia Hadith</th>
                <th>Similarity</th>
                <th>Variant Type</th>
                <th>Cross-Sect</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((pair, idx) => (
                <tr key={`${pair.hadith_a_id}-${pair.hadith_b_id}-${idx}`}>
                  <td
                    style={{ cursor: 'pointer', color: 'var(--color-primary)' }}
                    onClick={() => navigate(`/hadiths/${pair.hadith_a_id}`)}
                  >
                    {pair.hadith_a_id}
                    <br />
                    <small style={{ color: 'var(--color-muted-foreground)' }}>{pair.hadith_a_corpus}</small>
                  </td>
                  <td
                    style={{ cursor: 'pointer', color: 'var(--color-primary)' }}
                    onClick={() => navigate(`/hadiths/${pair.hadith_b_id}`)}
                  >
                    {pair.hadith_b_id}
                    <br />
                    <small style={{ color: 'var(--color-muted-foreground)' }}>{pair.hadith_b_corpus}</small>
                  </td>
                  <td>
                    {pair.similarity_score != null ? (
                      <span className={pair.similarity_score > 0.8 ? 'badge-similarity-high' : 'badge-similarity-low'}>
                        {(pair.similarity_score * 100).toFixed(1)}%
                      </span>
                    ) : (
                      '-'
                    )}
                  </td>
                  <td>{pair.variant_type ?? '-'}</td>
                  <td>{pair.cross_sect ? 'Yes' : 'No'}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="pagination">
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
