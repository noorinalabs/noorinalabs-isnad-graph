import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { searchAll, searchSemantic } from '../api/client'
import { Card, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Input } from '../components/ui/Input'
import { Button } from '../components/ui/Button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../components/ui/Dialog'

type SearchMode = 'fulltext' | 'semantic'
type SortOption = 'relevance' | 'date-asc' | 'date-desc' | 'name-en' | 'name-ar'
type EntityType = 'narrator' | 'hadith' | 'collection'

interface SearchFilters {
  entityTypes: EntityType[]
  collections: string[]
  gradings: string[]
  centuries: number[]
  topics: string[]
}

const COLLECTIONS = [
  'Bukhari',
  'Muslim',
  'Abu Dawud',
  'Tirmidhi',
  "Nasa'i",
  'Ibn Majah',
  'al-Kafi',
  'Bihar al-Anwar',
]

const GRADINGS = ['Sahih', 'Hasan', "Da'if", "Mawdu'"]
const CENTURIES = [1, 2, 3, 4, 5]
const TOPICS = [
  'Jurisprudence (fiqh)',
  'Theology (aqidah)',
  'Ethics (akhlaq)',
  'Worship (ibadah)',
  'History (sira)',
  'Eschatology',
]

const SUGGESTED_QUERIES = [
  'Abu Hurayra',
  'الأعمال بالنيات',
  'Sahih al-Bukhari',
  'prayer',
]

const DEFAULT_FILTERS: SearchFilters = {
  entityTypes: ['narrator', 'hadith', 'collection'],
  collections: [],
  gradings: [],
  centuries: [],
  topics: [],
}

const RESULTS_PER_PAGE = 10

function hasActiveFilters(filters: SearchFilters): boolean {
  return (
    filters.entityTypes.length < 3 ||
    filters.collections.length > 0 ||
    filters.gradings.length > 0 ||
    filters.centuries.length > 0 ||
    filters.topics.length > 0
  )
}

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [inputValue, setInputValue] = useState(searchParams.get('q') ?? '')
  const [query, setQuery] = useState(searchParams.get('q') ?? '')
  const [mode, setMode] = useState<SearchMode>('fulltext')
  const [sort, setSort] = useState<SortOption>('relevance')
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState<SearchFilters>(DEFAULT_FILTERS)
  const [showTypeahead, setShowTypeahead] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const navigate = useNavigate()
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const inputRef = useRef<HTMLInputElement>(null)
  const typeaheadRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setQuery(inputValue)
      setPage(1)
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [inputValue])

  useEffect(() => {
    if (query) {
      setSearchParams({ q: query, page: String(page) }, { replace: true })
    }
  }, [query, page, setSearchParams])

  // Typeahead query (limited results for dropdown)
  const { data: typeaheadData } = useQuery({
    queryKey: ['search-typeahead', inputValue, mode],
    queryFn: () =>
      mode === 'semantic' ? searchSemantic(inputValue, 9) : searchAll(inputValue, 9),
    enabled: inputValue.length >= 2 && showTypeahead,
  })

  // Full search query
  const { data: searchData, isLoading, isError } = useQuery({
    queryKey: ['search', query, mode],
    queryFn: () =>
      mode === 'semantic' ? searchSemantic(query, 200) : searchAll(query, 200),
    enabled: query.length >= 2,
  })

  // Close typeahead on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        typeaheadRef.current &&
        !typeaheadRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setShowTypeahead(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Keyboard shortcut: / to focus search
  useEffect(() => {
    function handleSlash(e: KeyboardEvent) {
      if (e.key === '/' && document.activeElement !== inputRef.current) {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    document.addEventListener('keydown', handleSlash)
    return () => document.removeEventListener('keydown', handleSlash)
  }, [])

  const handleResultClick = useCallback(
    (result: { type: string; id: string }) => {
      setShowTypeahead(false)
      if (result.type === 'narrator') navigate(`/narrators/${result.id}`)
      else if (result.type === 'hadith') navigate(`/hadiths/${result.id}`)
      else if (result.type === 'collection') navigate(`/collections/${result.id}`)
    },
    [navigate],
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setQuery(inputValue)
    setShowTypeahead(false)
    setPage(1)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showTypeahead || !typeaheadData) return
    const items = typeaheadData.results
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((prev) => Math.min(prev + 1, items.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((prev) => Math.max(prev - 1, -1))
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault()
      const item = items[activeIndex]
      if (item) handleResultClick(item)
    } else if (e.key === 'Escape') {
      setShowTypeahead(false)
    }
  }

  const toggleEntityType = (type: EntityType) => {
    setFilters((prev) => {
      const types = prev.entityTypes.includes(type)
        ? prev.entityTypes.filter((t) => t !== type)
        : [...prev.entityTypes, type]
      if (types.length === 0) return prev
      return { ...prev, entityTypes: types }
    })
    setPage(1)
  }

  const toggleFilter = (
    key: 'collections' | 'gradings' | 'topics',
    value: string,
  ) => {
    setFilters((prev) => {
      const arr = prev[key]
      const next = arr.includes(value)
        ? arr.filter((v) => v !== value)
        : [...arr, value]
      return { ...prev, [key]: next }
    })
    setPage(1)
  }

  const toggleCentury = (century: number) => {
    setFilters((prev) => {
      const next = prev.centuries.includes(century)
        ? prev.centuries.filter((c) => c !== century)
        : [...prev.centuries, century]
      return { ...prev, centuries: next }
    })
    setPage(1)
  }

  // Client-side filtering of results
  const filteredResults = (searchData?.results ?? []).filter((r) => {
    if (!filters.entityTypes.includes(r.type as EntityType)) return false
    return true
  })

  // Client-side sort
  const sortedResults = [...filteredResults].sort((a, b) => {
    if (sort === 'relevance') return b.score - a.score
    if (sort === 'name-en') return a.title.localeCompare(b.title)
    if (sort === 'name-ar') return (a.title_ar ?? '').localeCompare(b.title_ar ?? '', 'ar')
    return 0
  })

  const totalPages = Math.ceil(sortedResults.length / RESULTS_PER_PAGE)
  const paginatedResults = sortedResults.slice(
    (page - 1) * RESULTS_PER_PAGE,
    page * RESULTS_PER_PAGE,
  )

  const activeFilterCount =
    (filters.entityTypes.length < 3 ? 1 : 0) +
    (filters.collections.length > 0 ? 1 : 0) +
    (filters.gradings.length > 0 ? 1 : 0) +
    (filters.centuries.length > 0 ? 1 : 0) +
    (filters.topics.length > 0 ? 1 : 0)

  // Group typeahead by type
  const typeaheadGroups = typeaheadData
    ? {
        narrator: typeaheadData.results.filter((r) => r.type === 'narrator').slice(0, 3),
        hadith: typeaheadData.results.filter((r) => r.type === 'hadith').slice(0, 3),
        collection: typeaheadData.results.filter((r) => r.type === 'collection').slice(0, 3),
      }
    : null

  const filterSidebar = (
    <div className="flex flex-col gap-5">
      {/* Entity type filter */}
      <div role="group" aria-labelledby="filter-entity-type">
        <h4 id="filter-entity-type" className="text-sm font-semibold mb-2 uppercase tracking-wide text-muted-foreground">
          Entity Type
        </h4>
        {(['narrator', 'hadith', 'collection'] as EntityType[]).map((type) => (
          <label key={type} className="flex items-center gap-2 py-1 cursor-pointer text-sm">
            <input
              type="checkbox"
              checked={filters.entityTypes.includes(type)}
              onChange={() => toggleEntityType(type)}
              className="rounded"
            />
            <span className="capitalize">{type}</span>
            <span className="text-muted-foreground ms-auto">
              ({searchData?.results.filter((r) => r.type === type).length ?? 0})
            </span>
          </label>
        ))}
      </div>

      {/* Collection filter */}
      <div role="group" aria-labelledby="filter-collection">
        <h4 id="filter-collection" className="text-sm font-semibold mb-2 uppercase tracking-wide text-muted-foreground">
          Collection
        </h4>
        {COLLECTIONS.map((c) => (
          <label key={c} className="flex items-center gap-2 py-1 cursor-pointer text-sm">
            <input
              type="checkbox"
              checked={filters.collections.includes(c)}
              onChange={() => toggleFilter('collections', c)}
              className="rounded"
            />
            {c}
          </label>
        ))}
      </div>

      {/* Grading filter */}
      <div role="group" aria-labelledby="filter-grading">
        <h4 id="filter-grading" className="text-sm font-semibold mb-2 uppercase tracking-wide text-muted-foreground">
          Grading
        </h4>
        {GRADINGS.map((g) => (
          <label key={g} className="flex items-center gap-2 py-1 cursor-pointer text-sm">
            <input
              type="checkbox"
              checked={filters.gradings.includes(g)}
              onChange={() => toggleFilter('gradings', g)}
              className="rounded"
            />
            {g}
          </label>
        ))}
      </div>

      {/* Century filter */}
      <div role="group" aria-labelledby="filter-century">
        <h4 id="filter-century" className="text-sm font-semibold mb-2 uppercase tracking-wide text-muted-foreground">
          Century (AH)
        </h4>
        <div className="flex flex-wrap gap-1">
          {CENTURIES.map((c) => (
            <Button
              key={c}
              variant={filters.centuries.includes(c) ? 'default' : 'outline'}
              size="sm"
              onClick={() => toggleCentury(c)}
            >
              {c === 5 ? '5th+' : `${c}${c === 1 ? 'st' : c === 2 ? 'nd' : c === 3 ? 'rd' : 'th'}`}
            </Button>
          ))}
        </div>
      </div>

      {/* Topic filter */}
      {filters.entityTypes.includes('hadith') && (
        <div role="group" aria-labelledby="filter-topic">
          <h4 id="filter-topic" className="text-sm font-semibold mb-2 uppercase tracking-wide text-muted-foreground">
            Topic
          </h4>
          {TOPICS.map((t) => (
            <label key={t} className="flex items-center gap-2 py-1 cursor-pointer text-sm">
              <input
                type="checkbox"
                checked={filters.topics.includes(t)}
                onChange={() => toggleFilter('topics', t)}
                className="rounded"
              />
              {t}
            </label>
          ))}
        </div>
      )}

      {/* Clear filters */}
      {hasActiveFilters(filters) && (
        <Button
          variant="ghost"
          className="w-full"
          onClick={() => {
            setFilters(DEFAULT_FILTERS)
            setPage(1)
          }}
        >
          Clear all filters
        </Button>
      )}
    </div>
  )

  return (
    <div className="max-w-7xl mx-auto">
      <h2 className="page-heading">Search</h2>

      {/* Search bar */}
      <form onSubmit={handleSubmit} className="mb-4">
        <div className="relative">
          <div className="flex gap-2 items-center">
            <div className="relative flex-1 max-w-xl">
              <Input
                ref={inputRef}
                type="text"
                role="combobox"
                aria-expanded={showTypeahead && !!typeaheadGroups}
                aria-haspopup="listbox"
                aria-autocomplete="list"
                aria-activedescendant={activeIndex >= 0 ? `typeahead-${activeIndex}` : undefined}
                placeholder="Search hadith, narrators, collections..."
                value={inputValue}
                onChange={(e) => {
                  setInputValue(e.target.value)
                  setShowTypeahead(true)
                  setActiveIndex(-1)
                }}
                onFocus={() => setShowTypeahead(true)}
                onKeyDown={handleKeyDown}
                className="h-12 text-base ps-10"
              />
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="absolute start-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                aria-hidden="true"
              >
                <circle cx="11" cy="11" r="8" />
                <path d="m21 21-4.3-4.3" />
              </svg>
              {inputValue && (
                <button
                  type="button"
                  onClick={() => {
                    setInputValue('')
                    setQuery('')
                    inputRef.current?.focus()
                  }}
                  className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label="Clear search"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M18 6 6 18" />
                    <path d="m6 6 12 12" />
                  </svg>
                </button>
              )}
            </div>
            <Button type="submit">Search</Button>
          </div>

          {/* Search mode toggle */}
          <div className="flex gap-2 mt-2" role="radiogroup" aria-label="Search mode">
            <label className="flex items-center gap-1.5 text-sm cursor-pointer">
              <input
                type="radio"
                name="searchMode"
                checked={mode === 'fulltext'}
                onChange={() => setMode('fulltext')}
                className="accent-primary"
              />
              Full-text
            </label>
            <label className="flex items-center gap-1.5 text-sm cursor-pointer" title="Find hadith with similar meaning, even with different wording">
              <input
                type="radio"
                name="searchMode"
                checked={mode === 'semantic'}
                onChange={() => setMode('semantic')}
                className="accent-primary"
              />
              Semantic
            </label>
          </div>

          {/* Typeahead dropdown */}
          {showTypeahead && typeaheadGroups && inputValue.length >= 2 && (
            <div
              ref={typeaheadRef}
              role="listbox"
              className="absolute z-50 top-14 start-0 w-full max-w-xl bg-popover border rounded-md shadow-lg overflow-hidden"
            >
              {isLoading && (
                <div className="p-3 text-sm text-muted-foreground">Searching...</div>
              )}
              {!isLoading && (
                <>
                  {typeaheadGroups.narrator.length > 0 && (
                    <div>
                      <div className="px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide bg-muted/50">
                        Narrators
                      </div>
                      {typeaheadGroups.narrator.map((r, i) => {
                        const globalIndex = i
                        return (
                          <div
                            key={`${r.type}-${r.id}`}
                            id={`typeahead-${globalIndex}`}
                            role="option"
                            aria-selected={activeIndex === globalIndex}
                            className={`px-3 py-2 cursor-pointer hover:bg-accent/50 flex items-center justify-between ${activeIndex === globalIndex ? 'bg-accent/50' : ''}`}
                            onClick={() => handleResultClick(r)}
                          >
                            <span className="text-sm font-medium">{r.title}</span>
                            {r.title_ar && (
                              <bdi dir="rtl" lang="ar" className="text-sm text-muted-foreground">
                                {r.title_ar}
                              </bdi>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                  {typeaheadGroups.hadith.length > 0 && (
                    <div>
                      <div className="px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide bg-muted/50">
                        Hadith
                      </div>
                      {typeaheadGroups.hadith.map((r, i) => {
                        const globalIndex = typeaheadGroups.narrator.length + i
                        return (
                          <div
                            key={`${r.type}-${r.id}`}
                            id={`typeahead-${globalIndex}`}
                            role="option"
                            aria-selected={activeIndex === globalIndex}
                            className={`px-3 py-2 cursor-pointer hover:bg-accent/50 text-sm ${activeIndex === globalIndex ? 'bg-accent/50' : ''}`}
                            onClick={() => handleResultClick(r)}
                          >
                            <div className="font-medium truncate">{r.title}</div>
                            {r.title_ar && (
                              <div dir="rtl" lang="ar" className="text-muted-foreground truncate text-xs mt-0.5">
                                {r.title_ar}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                  {typeaheadGroups.collection.length > 0 && (
                    <div>
                      <div className="px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide bg-muted/50">
                        Collections
                      </div>
                      {typeaheadGroups.collection.map((r, i) => {
                        const globalIndex =
                          typeaheadGroups.narrator.length +
                          typeaheadGroups.hadith.length +
                          i
                        return (
                          <div
                            key={`${r.type}-${r.id}`}
                            id={`typeahead-${globalIndex}`}
                            role="option"
                            aria-selected={activeIndex === globalIndex}
                            className={`px-3 py-2 cursor-pointer hover:bg-accent/50 flex items-center justify-between text-sm ${activeIndex === globalIndex ? 'bg-accent/50' : ''}`}
                            onClick={() => handleResultClick(r)}
                          >
                            <span className="font-medium">{r.title}</span>
                            {r.title_ar && (
                              <bdi dir="rtl" lang="ar" className="text-muted-foreground">
                                {r.title_ar}
                              </bdi>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                  {typeaheadGroups.narrator.length === 0 &&
                    typeaheadGroups.hadith.length === 0 &&
                    typeaheadGroups.collection.length === 0 && (
                      <div className="p-3 text-sm text-muted-foreground">No suggestions</div>
                    )}
                </>
              )}
            </div>
          )}
        </div>
      </form>

      {/* No query — initial empty state */}
      {query.length < 2 && (
        <Card className="max-w-lg mx-auto mt-12 text-center">
          <CardContent className="py-12">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="mx-auto mb-4 text-muted-foreground"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.3-4.3" />
            </svg>
            <h3 className="text-lg font-semibold mb-2">Search the hadith corpus</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Enter a narrator name, hadith text, or topic to begin exploring.
            </p>
            <div className="flex flex-wrap gap-2 justify-center">
              {SUGGESTED_QUERIES.map((sq) => (
                <Button
                  key={sq}
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setInputValue(sq)
                    setQuery(sq)
                    setShowTypeahead(false)
                  }}
                >
                  <bdi>{sq}</bdi>
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Results layout */}
      {query.length >= 2 && (
        <div className="flex gap-6">
          {/* Filter sidebar — desktop */}
          <aside className="hidden lg:block w-[260px] shrink-0">
            {filterSidebar}
          </aside>

          {/* Filter modal trigger — tablet/mobile */}
          <Dialog open={filtersOpen} onOpenChange={setFiltersOpen}>
            <DialogTrigger asChild>
              <Button
                variant="outline"
                className="lg:hidden fixed bottom-4 end-4 z-40 shadow-lg"
              >
                Filters{activeFilterCount > 0 ? ` (${activeFilterCount})` : ''}
              </Button>
            </DialogTrigger>
            <DialogContent className="max-h-[80vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Filters</DialogTitle>
              </DialogHeader>
              {filterSidebar}
            </DialogContent>
          </Dialog>

          {/* Results area */}
          <div className="flex-1 min-w-0">
            {/* Results header */}
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
              <div className="text-sm text-muted-foreground" aria-live="polite">
                Showing {sortedResults.length} results for{' '}
                <bdi dir="auto" className="font-medium text-foreground">
                  &quot;{query}&quot;
                </bdi>
              </div>
              <Select value={sort} onValueChange={(v) => setSort(v as SortOption)}>
                <SelectTrigger className="w-40">
                  <SelectValue placeholder="Sort by" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="relevance">Relevance</SelectItem>
                  <SelectItem value="date-asc">Date (oldest)</SelectItem>
                  <SelectItem value="date-desc">Date (newest)</SelectItem>
                  <SelectItem value="name-en">Name (A-Z)</SelectItem>
                  <SelectItem value="name-ar">Name (ا-ي)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Loading */}
            {isLoading && (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Card key={i} className="animate-pulse">
                    <CardContent className="py-4">
                      <div className="h-4 bg-muted rounded w-1/4 mb-3" />
                      <div className="h-5 bg-muted rounded w-3/4 mb-2" />
                      <div className="h-4 bg-muted rounded w-1/2" />
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}

            {/* Error */}
            {isError && (
              <Card className="text-center">
                <CardContent className="py-8">
                  <p className="mb-2">Search failed. Please try again.</p>
                  <Button
                    variant="outline"
                    onClick={() => setQuery(inputValue)}
                  >
                    Retry
                  </Button>
                </CardContent>
              </Card>
            )}

            {/* No results */}
            {!isLoading && !isError && sortedResults.length === 0 && query.length >= 2 && (
              <Card className="text-center">
                <CardContent className="py-8">
                  <p className="font-medium mb-3">
                    No results found for &quot;{query}&quot;
                  </p>
                  <ul className="text-sm text-muted-foreground text-start max-w-sm mx-auto space-y-1">
                    <li>Try Arabic script: type the name in Arabic for more precise matching</li>
                    <li>Check transliteration: Abu vs. Aboo, al- vs. el-</li>
                    {mode === 'fulltext' && (
                      <li>Try semantic search: toggle to find similar meanings</li>
                    )}
                    {hasActiveFilters(filters) && (
                      <li>Broaden filters: you have {activeFilterCount} active filter(s) narrowing results</li>
                    )}
                  </ul>
                  {hasActiveFilters(filters) && (
                    <Button
                      variant="outline"
                      className="mt-4"
                      onClick={() => setFilters(DEFAULT_FILTERS)}
                    >
                      Clear all filters
                    </Button>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Result cards */}
            {!isLoading && !isError && paginatedResults.length > 0 && (
              <div className="space-y-3">
                {paginatedResults.map((r) => (
                  <ResultCard key={`${r.type}-${r.id}`} result={r} mode={mode} onClick={() => handleResultClick(r)} />
                ))}
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <nav aria-label="Search results pagination" className="flex items-center justify-center gap-1 mt-6">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Prev
                </Button>
                {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                  let pageNum: number
                  if (totalPages <= 7) {
                    pageNum = i + 1
                  } else if (page <= 4) {
                    pageNum = i + 1
                  } else if (page >= totalPages - 3) {
                    pageNum = totalPages - 6 + i
                  } else {
                    pageNum = page - 3 + i
                  }
                  return (
                    <Button
                      key={pageNum}
                      variant={pageNum === page ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setPage(pageNum)}
                    >
                      {pageNum}
                    </Button>
                  )
                })}
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </nav>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/* ───────────────────────────────────────────
 * Result card components
 * ─────────────────────────────────────────── */

function RelevanceBadge({ score }: { score: number }) {
  const level =
    score >= 0.9 ? 'text-sahih' : score >= 0.7 ? 'text-warning' : 'text-muted-foreground'
  return (
    <span className={`text-xs font-medium ${level}`}>
      {(score * 100).toFixed(0)}%
    </span>
  )
}

function ResultCard({
  result,
  mode,
  onClick,
}: {
  result: { type: string; id: string; title: string; title_ar: string; score: number }
  mode: SearchMode
  onClick: () => void
}) {
  const badgeVariant: Record<string, 'sunni' | 'shia' | 'sahih' | 'outline'> = {
    narrator: 'sunni',
    hadith: 'shia',
    collection: 'outline',
  }

  return (
    <Card
      className="cursor-pointer transition-shadow hover:shadow-md"
      role="article"
      aria-label={`${result.type}: ${result.title}`}
      onClick={onClick}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter') onClick()
      }}
    >
      <CardContent className="py-4">
        <div className="flex items-center justify-between mb-2">
          <Badge variant={badgeVariant[result.type] ?? 'outline'} className="text-xs uppercase">
            {result.type}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {mode === 'semantic' ? 'Similarity' : 'Relevance'}:{' '}
            <RelevanceBadge score={result.score} />
          </span>
        </div>

        {result.title_ar && (
          <div dir="rtl" lang="ar" className="text-lg mb-1 font-arabic leading-relaxed">
            {result.title_ar}
          </div>
        )}

        <div className="font-medium">{result.title}</div>
      </CardContent>
    </Card>
  )
}
