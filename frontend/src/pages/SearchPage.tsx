import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { searchAll, searchSemantic } from '../api/client'

const typeBadgeClass: Record<string, string> = {
  narrator: 'badge-narrator',
  hadith: 'badge-hadith',
  collection: 'badge-collection',
}

export default function SearchPage() {
  const [inputValue, setInputValue] = useState('')
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<'fulltext' | 'semantic'>('fulltext')
  const navigate = useNavigate()
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setQuery(inputValue)
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [inputValue])

  const { data: searchData, isLoading } = useQuery({
    queryKey: ['search', query, mode],
    queryFn: () => (mode === 'semantic' ? searchSemantic(query) : searchAll(query)),
    enabled: query.length >= 2,
  })

  const results = searchData?.results

  const handleResultClick = (result: { type: string; id: string }) => {
    if (result.type === 'narrator') navigate(`/narrators/${result.id}`)
    else if (result.type === 'hadith') navigate(`/hadiths/${result.id}`)
    else if (result.type === 'collection') navigate(`/collections/${result.id}`)
  }

  return (
    <div>
      <h2>Search</h2>

      <div className="flex-row" style={{ marginBottom: '1rem' }}>
        <input
          type="text"
          placeholder="Search narrators, hadiths, collections..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          className="form-input"
          style={{ flex: 1, maxWidth: 500 }}
        />
        <label className="flex-row" style={{ gap: '0.25rem' }}>
          <input
            type="radio"
            checked={mode === 'fulltext'}
            onChange={() => setMode('fulltext')}
          />
          Full-text
        </label>
        <label className="flex-row" style={{ gap: '0.25rem' }}>
          <input
            type="radio"
            checked={mode === 'semantic'}
            onChange={() => setMode('semantic')}
          />
          Semantic
        </label>
      </div>

      {isLoading && <p>Searching...</p>}

      {results && results.length === 0 && query.length >= 2 && (
        <p className="muted-text">No results found for &quot;{query}&quot;</p>
      )}

      {results && results.length > 0 && (
        <div>
          {results.map((r) => (
            <div
              key={`${r.type}-${r.id}`}
              onClick={() => handleResultClick(r)}
              className="search-result"
            >
              <div className="flex-row">
                <span
                  className={`badge-sm ${typeBadgeClass[r.type] ?? ''}`}
                  style={{ fontWeight: 600, textTransform: 'capitalize' }}
                >
                  {r.type}
                </span>
                <span style={{ fontWeight: 500 }}>{r.title}</span>
              </div>
              {r.title_ar && (
                <p className="text-rtl" style={{ margin: '0.25rem 0 0', color: '#666', fontSize: '0.9rem' }}>
                  {r.title_ar}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
