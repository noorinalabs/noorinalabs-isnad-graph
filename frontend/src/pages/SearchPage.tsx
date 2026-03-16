import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { searchAll, searchSemantic } from '../api/client'

export default function SearchPage() {
  const [inputValue, setInputValue] = useState('')
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<'fulltext' | 'semantic'>('fulltext')
  const navigate = useNavigate()
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

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

  const typeBadgeColor: Record<string, { bg: string; fg: string }> = {
    narrator: { bg: '#e8f5e9', fg: '#2e7d32' },
    hadith: { bg: '#e3f2fd', fg: '#1565c0' },
    collection: { bg: '#fce4ec', fg: '#c62828' },
  }

  return (
    <div>
      <h2>Search</h2>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', alignItems: 'center' }}>
        <input
          type="text"
          placeholder="Search narrators, hadiths, collections..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          style={{ padding: '0.5rem', flex: 1, maxWidth: 500 }}
        />
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <input
            type="radio"
            checked={mode === 'fulltext'}
            onChange={() => setMode('fulltext')}
          />
          Full-text
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
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
        <p style={{ color: '#666' }}>No results found for &quot;{query}&quot;</p>
      )}

      {results && results.length > 0 && (
        <div>
          {results.map((r) => {
            const badge = typeBadgeColor[r.type] ?? { bg: '#eee', fg: '#333' }
            return (
              <div
                key={`${r.type}-${r.id}`}
                onClick={() => handleResultClick(r)}
                style={{
                  padding: '0.75rem',
                  borderBottom: '1px solid #eee',
                  cursor: 'pointer',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span
                    style={{
                      padding: '0.1rem 0.4rem',
                      borderRadius: 3,
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      background: badge.bg,
                      color: badge.fg,
                      textTransform: 'capitalize',
                    }}
                  >
                    {r.type}
                  </span>
                  <span style={{ fontWeight: 500 }}>{r.title}</span>
                </div>
                {r.title_ar && (
                  <p
                    style={{
                      margin: '0.25rem 0 0',
                      color: '#666',
                      fontSize: '0.9rem',
                      direction: 'rtl',
                    }}
                  >
                    {r.title_ar}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
