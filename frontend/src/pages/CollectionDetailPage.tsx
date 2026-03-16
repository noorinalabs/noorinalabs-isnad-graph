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
  if (error) return <p style={{ color: 'red' }}>Error: {(error as Error).message}</p>
  if (!collection) return <p>Collection not found.</p>

  const isSunni = collection.sect.toLowerCase() === 'sunni'

  return (
    <div>
      <Link to="/collections" style={{ color: '#1a73e8' }}>
        &larr; Back to Collections
      </Link>

      <h2 style={{ marginTop: '1rem' }}>
        {collection.name_en}
        <span
          style={{
            marginLeft: '0.75rem',
            padding: '0.15rem 0.5rem',
            borderRadius: 4,
            fontSize: '0.9rem',
            fontWeight: 600,
            background: isSunni ? '#e8f5e9' : '#e3f2fd',
            color: isSunni ? '#2e7d32' : '#1565c0',
          }}
        >
          {collection.sect}
        </span>
      </h2>

      <p style={{ direction: 'rtl', textAlign: 'right', fontSize: '1.1rem', color: '#555' }}>
        {collection.name_ar}
      </p>

      <div style={{ color: '#666', marginBottom: '1.5rem' }}>
        {collection.compiler_name && <span>Compiler: {collection.compiler_name}</span>}
        {collection.compiler_name && <span style={{ margin: '0 0.5rem' }}>|</span>}
        {collection.compilation_year_ah != null && (
          <span>Compiled: {collection.compilation_year_ah} AH</span>
        )}
        {collection.compilation_year_ah != null && (
          <span style={{ margin: '0 0.5rem' }}>|</span>
        )}
        <span>{collection.total_hadiths != null ? collection.total_hadiths.toLocaleString() : '?'} hadiths</span>
        {collection.book_count != null && (
          <>
            <span style={{ margin: '0 0.5rem' }}>|</span>
            <span>{collection.book_count} books</span>
          </>
        )}
      </div>
    </div>
  )
}
