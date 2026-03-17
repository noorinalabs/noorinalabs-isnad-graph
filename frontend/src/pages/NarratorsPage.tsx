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

      <div className="flex-row" style={{ marginBottom: '1rem' }}>
        <input
          type="text"
          placeholder="Search narrators..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="form-input"
          style={{ flex: 1, maxWidth: 400 }}
        />
        <button onClick={handleSearch} className="btn">
          Search
        </button>
      </div>

      {isLoading && <p>Loading...</p>}
      {error && <p className="error-text">Error: {(error as Error).message}</p>}

      {data && (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Name (Arabic)</th>
                <th>Name (English)</th>
                <th>Generation</th>
                <th>Trustworthiness</th>
                <th>Community</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((n) => (
                <tr
                  key={n.id}
                  onClick={() => navigate(`/narrators/${n.id}`)}
                  className="clickable-row"
                >
                  <td className="text-rtl">{n.name_ar}</td>
                  <td>{n.name_en ?? '-'}</td>
                  <td>{n.generation ?? '-'}</td>
                  <td>{n.trustworthiness_consensus ?? '-'}</td>
                  <td>{n.community_id != null ? `#${n.community_id}` : '-'}</td>
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
