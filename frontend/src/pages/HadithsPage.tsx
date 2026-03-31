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
      <h2 className="page-heading">Hadiths</h2>

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
                <th>Source</th>
                <th>Grade</th>
                <th>Topics</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((h) => (
                <tr
                  key={h.id}
                  onClick={() => navigate(`/hadiths/${h.id}`)}
                  onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/hadiths/${h.id}`) }}
                  tabIndex={0}
                  role="link"
                  className="clickable-row"
                >
                  <td>{h.source_corpus}</td>
                  <td>
                    {h.grade_composite && (
                      <span
                        className={`badge ${h.grade_composite.toLowerCase() === 'sahih' ? 'badge-sahih' : 'badge-other-grade'}`}
                      >
                        {h.grade_composite}
                      </span>
                    )}
                  </td>
                  <td>
                    {h.topic_tags?.map((tag) => (
                      <span key={tag} className="badge-topic">
                        {tag}
                      </span>
                    ))}
                  </td>
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
