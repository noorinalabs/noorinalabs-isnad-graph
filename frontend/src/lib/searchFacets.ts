import type { SearchResult } from '../types/api'

/**
 * Client-side facet filtering for the search page (#1036).
 *
 * The search endpoints return a flat result list; the collection / grading /
 * century / topic facets are applied here over the result metadata the API now
 * carries on each {@link SearchResult}. This mirrors the page's existing
 * client-side entity-type filtering rather than introducing a server round-trip.
 *
 * Matching is *type-aware*: a facet only constrains result types it applies to
 * (collection → hadith + collection, grading → hadith, century → narrator,
 * topic → hadith). For non-applicable types the facet is ignored, so e.g.
 * filtering by collection narrows hadiths without dropping matching narrators.
 *
 * Matching is also *permissive on missing data*: a result whose applicable
 * attribute is null/empty is treated as "unknown" and is NOT excluded. This
 * keeps semantic hits (which lack graph-derived metadata) and partially-loaded
 * records visible instead of silently disappearing under an active facet.
 */
export interface FacetSelection {
  collections: string[]
  gradings: string[]
  centuries: number[]
  topics: string[]
}

interface FacetApplicability {
  collection: boolean
  grade: boolean
  century: boolean
  topic: boolean
}

const FACET_APPLIES: Record<string, FacetApplicability> = {
  hadith: { collection: true, grade: true, century: false, topic: true },
  collection: { collection: true, grade: false, century: false, topic: false },
  narrator: { collection: false, grade: false, century: true, topic: false },
}

const NO_FACETS: FacetApplicability = {
  collection: false,
  grade: false,
  century: false,
  topic: false,
}

/**
 * Normalize a label/value for tolerant comparison: lowercase, drop the various
 * apostrophe/hamza glyphs (so "Da'if" === "daif", "Mawdu'" === "mawdu"), and
 * collapse whitespace.
 */
function norm(value: string): string {
  return value
    .toLowerCase()
    .replace(/['’ʼʿ`´‘]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function matchesCollection(value: string | null | undefined, selected: string[]): boolean {
  if (selected.length === 0) return true
  if (!value) return true // unknown collection is not excluded
  const v = norm(value)
  return selected.some((label) => {
    const l = norm(label)
    return v === l || v.includes(l) || l.includes(v)
  })
}

function matchesGrade(value: string | null | undefined, selected: string[]): boolean {
  if (selected.length === 0) return true
  if (!value) return true
  // `value` is already a canonical token (e.g. "sahih", "daif", "hasan_sahih");
  // the facet labels normalize to the same tokens for the simple grades.
  const v = norm(value)
  return selected.some((label) => v === norm(label))
}

function matchesCentury(value: number | null | undefined, selected: number[]): boolean {
  if (selected.length === 0) return true
  if (value == null) return true
  // The largest facet bucket is open-ended ("5th+"), so it also matches later
  // centuries; smaller buckets are exact.
  const maxBucket = Math.max(...selected)
  return selected.some((c) => (c === maxBucket ? value >= c : value === c))
}

/**
 * Tokens a topic facet label can match against a hadith's `topic_tags`, e.g.
 * "Jurisprudence (fiqh)" -> ["fiqh", "jurisprudence"], "Eschatology" ->
 * ["eschatology"]. A tag matches if it contains, or is contained by, any token.
 */
function topicTokens(label: string): string[] {
  const tokens: string[] = []
  const captured = label.match(/\(([^)]+)\)/)?.[1]
  if (captured) tokens.push(norm(captured))
  const lead = norm(label.replace(/\([^)]*\)/, ''))
  if (lead) tokens.push(lead)
  return tokens
}

function matchesTopic(values: string[] | undefined, selected: string[]): boolean {
  if (selected.length === 0) return true
  if (!values || values.length === 0) return true
  const tags = values.map(norm).filter(Boolean)
  if (tags.length === 0) return true
  return selected.some((label) =>
    topicTokens(label).some((token) =>
      tags.some((tag) => tag.includes(token) || token.includes(tag)),
    ),
  )
}

/**
 * True when a search result passes every active facet group. An empty group
 * (no values selected) imposes no constraint.
 */
export function matchesFacets(result: SearchResult, facets: FacetSelection): boolean {
  const applies = FACET_APPLIES[result.type] ?? NO_FACETS
  if (applies.collection && !matchesCollection(result.collection, facets.collections)) {
    return false
  }
  if (applies.grade && !matchesGrade(result.grade, facets.gradings)) return false
  if (applies.century && !matchesCentury(result.century, facets.centuries)) return false
  if (applies.topic && !matchesTopic(result.topics, facets.topics)) return false
  return true
}
