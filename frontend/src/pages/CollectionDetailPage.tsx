import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchCollection } from '../api/client'

export default function CollectionDetailPage() {
  const { id } = useParams<{ id: string }>()

  const {
    data: collection,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['collection', id],
    queryFn: () => fetchCollection(id!),
    enabled: !!id,
  })

  if (isLoading) return <p>Loading...</p>
  if (error) return <p className="error-text">Error: {(error as Error).message}</p>
  if (!collection) return <p>Collection not found.</p>

  const isSunni = collection.sect.toLowerCase() === 'sunni'

  return (
    <div>
      <Link to="/collections" className="link-primary">
        &larr; Back to Collections
      </Link>

      <h2 style={{ marginTop: '1rem' }}>
        {collection.name_en}
        <span className={`badge ${isSunni ? 'badge-sunni' : 'badge-shia'}`} style={{ marginLeft: '0.75rem', fontSize: '0.9rem' }}>
          {collection.sect}
        </span>
      </h2>

      <p className="text-rtl" style={{ fontSize: '1.1rem', color: '#555' }}>
        {collection.name_ar}
      </p>

      <div className="collection-meta">
        {collection.compiler_name && <span>Compiler: {collection.compiler_name}</span>}
        {collection.compiler_name && <span className="separator">|</span>}
        {collection.compilation_year_ah != null && (
          <span>Compiled: {collection.compilation_year_ah} AH</span>
        )}
        {collection.compilation_year_ah != null && <span className="separator">|</span>}
        <span>{collection.total_hadiths != null ? collection.total_hadiths.toLocaleString() : '?'} hadiths</span>
        {collection.book_count != null && (
          <>
            <span className="separator">|</span>
            <span>{collection.book_count} books</span>
          </>
        )}
      </div>
    </div>
  )
}
