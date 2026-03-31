import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchHadiths, fetchCollections } from '../api/client'

const PAGE_SIZES = [25, 50, 100] as const

export default function HadithsPage() {
  const [page, setPage] = useState(1)
  const [limit, setLimit] = useState<number>(25)
  const [searchInput, setSearchInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [collection, setCollection] = useState('')
  const [sourceCorpus, setSourceCorpus] = useState('')
  const [grade, setGrade] = useState('')
  const [jumpPage, setJumpPage] = useState('')
  const navigate = useNavigate()

  const filters = useMemo(
    () => ({
      collection: collection || undefined,
      source_corpus: sourceCorpus || undefined,
      grade: grade || undefined,
      q: searchQuery || undefined,
    }),
    [collection, sourceCorpus, grade, searchQuery],
  )

  const { data, isLoading, error } = useQuery({
    queryKey: ['hadiths', page, limit, filters],
    queryFn: () => fetchHadiths(page, limit, filters),
  })

  // Fetch collections for the filter dropdown
  const { data: collectionsData } = useQuery({
    queryKey: ['collections-all'],
    queryFn: () => fetchCollections(1, 100),
  })

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearchQuery(searchInput)
    setPage(1)
  }

  const handleFilterChange = (setter: (v: string) => void) => (
    e: React.ChangeEvent<HTMLSelectElement>,
  ) => {
    setter(e.target.value)
    setPage(1)
  }

  const handleJumpToPage = (e: React.FormEvent) => {
    e.preventDefault()
    const target = parseInt(jumpPage, 10)
    if (target >= 1 && target <= totalPages) {
      setPage(target)
      setJumpPage('')
    }
  }

  const clearFilters = () => {
    setCollection('')
    setSourceCorpus('')
    setGrade('')
    setSearchInput('')
    setSearchQuery('')
    setPage(1)
  }

  const hasActiveFilters = collection || sourceCorpus || grade || searchQuery

  // Determine which columns have data
  const hasGrades = data?.items.some((h) => h.grade_composite) ?? false
  const hasTopics = data?.items.some((h) => h.topic_tags && h.topic_tags.length > 0) ?? false

  const sourceCorpusOptions = ['lk', 'sunnah', 'thaqalayn', 'fawaz', 'sanadset', 'open_hadith', 'muhaddithat']

  return (
    <div>
      <h2 className="page-heading">Hadiths</h2>

      {/* Filter controls */}
      <div className="mb-4" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'flex-end' }}>
        {/* Text search */}
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            type="text"
            placeholder="Search hadith text..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="filter-input"
            style={{
              padding: '0.5rem 0.75rem',
              border: '1px solid var(--color-border)',
              borderRadius: '0.375rem',
              background: 'var(--color-background)',
              color: 'var(--color-foreground)',
              minWidth: '200px',
            }}
          />
          <button
            type="submit"
            className="btn btn-primary"
            style={{
              padding: '0.5rem 1rem',
              borderRadius: '0.375rem',
              background: 'var(--color-primary)',
              color: 'var(--color-primary-foreground)',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            Search
          </button>
        </form>

        {/* Collection filter */}
        <select
          value={collection}
          onChange={handleFilterChange(setCollection)}
          style={{
            padding: '0.5rem 0.75rem',
            border: '1px solid var(--color-border)',
            borderRadius: '0.375rem',
            background: 'var(--color-background)',
            color: 'var(--color-foreground)',
          }}
        >
          <option value="">All Collections</option>
          {collectionsData?.items.map((c) => (
            <option key={c.id} value={c.name_en}>
              {c.name_en}
            </option>
          ))}
        </select>

        {/* Source corpus filter */}
        <select
          value={sourceCorpus}
          onChange={handleFilterChange(setSourceCorpus)}
          style={{
            padding: '0.5rem 0.75rem',
            border: '1px solid var(--color-border)',
            borderRadius: '0.375rem',
            background: 'var(--color-background)',
            color: 'var(--color-foreground)',
          }}
        >
          <option value="">All Sources</option>
          {sourceCorpusOptions.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>

        {/* Grade filter */}
        <select
          value={grade}
          onChange={handleFilterChange(setGrade)}
          style={{
            padding: '0.5rem 0.75rem',
            border: '1px solid var(--color-border)',
            borderRadius: '0.375rem',
            background: 'var(--color-background)',
            color: 'var(--color-foreground)',
          }}
        >
          <option value="">All Grades</option>
          <option value="sahih">Sahih</option>
          <option value="hasan">Hasan</option>
          <option value="da'if">Da'if</option>
          <option value="mawdu'">Mawdu'</option>
        </select>

        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            style={{
              padding: '0.5rem 1rem',
              borderRadius: '0.375rem',
              background: 'transparent',
              color: 'var(--color-muted-foreground)',
              border: '1px solid var(--color-border)',
              cursor: 'pointer',
            }}
          >
            Clear filters
          </button>
        )}
      </div>

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
          {/* Results summary */}
          <p className="text-sm mb-2" style={{ color: 'var(--color-muted-foreground)' }}>
            {data.total.toLocaleString()} hadith{data.total !== 1 ? 's' : ''} found
            {hasActiveFilters ? ' (filtered)' : ''}
          </p>

          <table className="data-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Source</th>
                {hasGrades && <th>Grade</th>}
                {hasTopics && <th>Topics</th>}
              </tr>
            </thead>
            <tbody>
              {data.items.map((h) => (
                <tr
                  key={h.id}
                  onClick={() => navigate(`/hadiths/${h.id}`)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') navigate(`/hadiths/${h.id}`)
                  }}
                  tabIndex={0}
                  role="link"
                  className="clickable-row"
                >
                  <td>{h.display_title || h.id}</td>
                  <td>{h.source_corpus}</td>
                  {hasGrades && (
                    <td>
                      {h.grade_composite && (
                        <span
                          className={`badge ${h.grade_composite.toLowerCase() === 'sahih' ? 'badge-sahih' : 'badge-other-grade'}`}
                        >
                          {h.grade_composite}
                        </span>
                      )}
                    </td>
                  )}
                  {hasTopics && (
                    <td>
                      {h.topic_tags?.map((tag) => (
                        <span key={tag} className="badge-topic">
                          {tag}
                        </span>
                      ))}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination */}
          <div className="pagination" style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap', marginTop: '1rem' }}>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <button disabled={page <= 1} onClick={() => setPage(1)}>
                First
              </button>
              <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Previous
              </button>
              <span>
                Page {data.page} of {totalPages.toLocaleString()}
              </span>
              <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                Next
              </button>
              <button disabled={page >= totalPages} onClick={() => setPage(totalPages)}>
                Last
              </button>
            </div>

            {/* Jump to page */}
            <form onSubmit={handleJumpToPage} style={{ display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
              <input
                type="number"
                min={1}
                max={totalPages}
                value={jumpPage}
                onChange={(e) => setJumpPage(e.target.value)}
                placeholder="Page #"
                style={{
                  width: '5rem',
                  padding: '0.25rem 0.5rem',
                  border: '1px solid var(--color-border)',
                  borderRadius: '0.375rem',
                  background: 'var(--color-background)',
                  color: 'var(--color-foreground)',
                }}
              />
              <button type="submit">Go</button>
            </form>

            {/* Page size selector */}
            <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
              <span style={{ color: 'var(--color-muted-foreground)', fontSize: '0.875rem' }}>Show:</span>
              {PAGE_SIZES.map((size) => (
                <button
                  key={size}
                  onClick={() => {
                    setLimit(size)
                    setPage(1)
                  }}
                  style={{
                    fontWeight: limit === size ? 'bold' : 'normal',
                    textDecoration: limit === size ? 'underline' : 'none',
                  }}
                >
                  {size}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
