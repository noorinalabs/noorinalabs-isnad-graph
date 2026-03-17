import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchCollections } from '../api/client'

export default function CollectionsPage() {
  const navigate = useNavigate()

  const { data, isLoading, error } = useQuery({
    queryKey: ['collections'],
    queryFn: () => fetchCollections(),
  })

  return (
    <div>
      <h2>Collections</h2>

      {isLoading && <p>Loading...</p>}
      {error && <p className="error-text">Error: {(error as Error).message}</p>}

      {data && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Name (Arabic)</th>
              <th>Name (English)</th>
              <th>Compiler</th>
              <th>Sect</th>
              <th style={{ textAlign: 'right' }}>Hadiths</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((c) => (
              <tr
                key={c.id}
                onClick={() => navigate(`/collections/${c.id}`)}
                className="clickable-row"
              >
                <td className="text-rtl">{c.name_ar}</td>
                <td>{c.name_en}</td>
                <td>{c.compiler_name ?? '-'}</td>
                <td>
                  <span className={`badge ${c.sect.toLowerCase() === 'sunni' ? 'badge-sunni' : 'badge-shia'}`}>
                    {c.sect}
                  </span>
                </td>
                <td style={{ textAlign: 'right' }}>
                  {c.total_hadiths != null ? c.total_hadiths.toLocaleString() : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
