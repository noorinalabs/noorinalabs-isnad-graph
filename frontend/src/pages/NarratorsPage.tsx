import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchNarrators } from '../api/client'

export default function NarratorsPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [inputValue, setInputValue] = useState('')
  const navigate = useNavigate()

  const { data, isLoading, error } = useQuery({
    queryKey: ['narrators', page, search],
    queryFn: () => fetchNarrators(page, 20, search || undefined),
  })

  const handleSearch = () => {
    setSearch(inputValue)
    setPage(1)
  }

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0

  return (
    <div>
      <h2>Narrators</h2>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <input
          type="text"
          placeholder="Search narrators..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          style={{ padding: '0.5rem', flex: 1, maxWidth: 400 }}
        />
        <button onClick={handleSearch} style={{ padding: '0.5rem 1rem' }}>
          Search
        </button>
      </div>

      {isLoading && <p>Loading...</p>}
      {error && <p style={{ color: 'red' }}>Error: {(error as Error).message}</p>}

      {data && (
        <>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #ddd', textAlign: 'left' }}>
                <th style={{ padding: '0.5rem' }}>Name (Arabic)</th>
                <th style={{ padding: '0.5rem' }}>Name (English)</th>
                <th style={{ padding: '0.5rem' }}>Generation</th>
                <th style={{ padding: '0.5rem' }}>Trustworthiness</th>
                <th style={{ padding: '0.5rem' }}>Community</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((n) => (
                <tr
                  key={n.id}
                  onClick={() => navigate(`/narrators/${n.id}`)}
                  style={{ borderBottom: '1px solid #eee', cursor: 'pointer' }}
                >
                  <td style={{ padding: '0.5rem', direction: 'rtl' }}>{n.name_ar}</td>
                  <td style={{ padding: '0.5rem' }}>{n.name_en ?? '-'}</td>
                  <td style={{ padding: '0.5rem' }}>{n.generation ?? '-'}</td>
                  <td style={{ padding: '0.5rem' }}>{n.trustworthiness_consensus ?? '-'}</td>
                  <td style={{ padding: '0.5rem' }}>
                    {n.community_id != null ? `#${n.community_id}` : '-'}
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
