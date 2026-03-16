import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchHadiths } from '../api/client'

export default function HadithsPage() {
  const [page, setPage] = useState(1)
  const navigate = useNavigate()

  const { data, isLoading, error } = useQuery({
    queryKey: ['hadiths', page],
    queryFn: () => fetchHadiths(page, 20),
  })

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0

  return (
    <div>
      <h2>Hadiths</h2>

      {isLoading && <p>Loading...</p>}
      {error && <p style={{ color: 'red' }}>Error: {(error as Error).message}</p>}

      {data && (
        <>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #ddd', textAlign: 'left' }}>
                <th style={{ padding: '0.5rem' }}>Source</th>
                <th style={{ padding: '0.5rem' }}>Grade</th>
                <th style={{ padding: '0.5rem' }}>Topics</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((h) => (
                <tr
                  key={h.id}
                  onClick={() => navigate(`/hadiths/${h.id}`)}
                  style={{ borderBottom: '1px solid #eee', cursor: 'pointer' }}
                >
                  <td style={{ padding: '0.5rem' }}>{h.source_corpus}</td>
                  <td style={{ padding: '0.5rem' }}>
                    {h.grade_composite && (
                      <span
                        style={{
                          padding: '0.15rem 0.5rem',
                          borderRadius: 4,
                          fontSize: '0.85rem',
                          background:
                            h.grade_composite.toLowerCase() === 'sahih' ? '#e6f4ea' : '#fef7e0',
                          color:
                            h.grade_composite.toLowerCase() === 'sahih' ? '#137333' : '#b06000',
                        }}
                      >
                        {h.grade_composite}
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '0.5rem' }}>
                    {h.topic_tags?.map((tag) => (
                      <span
                        key={tag}
                        style={{
                          display: 'inline-block',
                          marginRight: '0.25rem',
                          padding: '0.1rem 0.4rem',
                          borderRadius: 3,
                          fontSize: '0.8rem',
                          background: '#e8eaf6',
                          color: '#283593',
                        }}
                      >
                        {tag}
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
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
