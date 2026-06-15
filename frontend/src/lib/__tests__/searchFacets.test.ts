import { describe, it, expect } from 'vitest'
import { matchesFacets, type FacetSelection } from '../searchFacets'
import type { SearchResult } from '../../types/api'

const NO_FACETS: FacetSelection = {
  collections: [],
  gradings: [],
  centuries: [],
  topics: [],
}

function result(overrides: Partial<SearchResult>): SearchResult {
  return {
    id: 'x',
    type: 'hadith',
    title: 'title',
    title_ar: 'عنوان',
    score: 1,
    ...overrides,
  }
}

describe('matchesFacets', () => {
  it('passes everything when no facets are selected', () => {
    expect(matchesFacets(result({ type: 'narrator' }), NO_FACETS)).toBe(true)
    expect(matchesFacets(result({ type: 'hadith' }), NO_FACETS)).toBe(true)
    expect(matchesFacets(result({ type: 'collection' }), NO_FACETS)).toBe(true)
  })

  describe('collection facet', () => {
    it('keeps a hadith whose collection matches the selected full name', () => {
      const r = result({ type: 'hadith', collection: 'Sahih al-Bukhari' })
      expect(matchesFacets(r, { ...NO_FACETS, collections: ['Sahih al-Bukhari'] })).toBe(true)
    })

    it('drops a hadith whose collection does not match', () => {
      const r = result({ type: 'hadith', collection: 'Sahih Muslim' })
      expect(matchesFacets(r, { ...NO_FACETS, collections: ['Sahih al-Bukhari'] })).toBe(false)
    })

    it('matches case-insensitively and on substring', () => {
      const r = result({ type: 'hadith', collection: 'Sahih al-Bukhari' })
      expect(matchesFacets(r, { ...NO_FACETS, collections: ['bukhari'] })).toBe(true)
    })

    it('keeps a hadith with unknown (null) collection', () => {
      const r = result({ type: 'hadith', collection: null })
      expect(matchesFacets(r, { ...NO_FACETS, collections: ['Sahih al-Bukhari'] })).toBe(true)
    })

    it('ignores the collection facet for narrators (not applicable)', () => {
      const r = result({ type: 'narrator' })
      expect(matchesFacets(r, { ...NO_FACETS, collections: ['Sahih al-Bukhari'] })).toBe(true)
    })
  })

  describe('grading facet', () => {
    it('matches a normalized grade token against the display label', () => {
      expect(
        matchesFacets(result({ grade: 'sahih' }), { ...NO_FACETS, gradings: ['Sahih'] }),
      ).toBe(true)
      // apostrophe in the label must not block the match
      expect(
        matchesFacets(result({ grade: 'daif' }), { ...NO_FACETS, gradings: ["Da'if"] }),
      ).toBe(true)
      expect(
        matchesFacets(result({ grade: 'mawdu' }), { ...NO_FACETS, gradings: ["Mawdu'"] }),
      ).toBe(true)
    })

    it('matches the previously-unreachable compound and defect grades by canonical token (#1062)', () => {
      // The search facet now stores canonical tokens, so the compound grade and
      // the defect grades that the old 4-label list omitted are selectable.
      expect(
        matchesFacets(result({ grade: 'hasan_sahih' }), { ...NO_FACETS, gradings: ['hasan_sahih'] }),
      ).toBe(true)
      expect(
        matchesFacets(result({ grade: 'munkar' }), { ...NO_FACETS, gradings: ['munkar'] }),
      ).toBe(true)
      expect(
        matchesFacets(result({ grade: 'shadh' }), { ...NO_FACETS, gradings: ['shadh'] }),
      ).toBe(true)
      // A compound-grade hadith is not caught by a plain "sahih" selection.
      expect(
        matchesFacets(result({ grade: 'hasan_sahih' }), { ...NO_FACETS, gradings: ['sahih'] }),
      ).toBe(false)
    })

    it('drops a hadith whose grade token does not match', () => {
      expect(
        matchesFacets(result({ grade: 'sahih' }), { ...NO_FACETS, gradings: ['Hasan'] }),
      ).toBe(false)
    })

    it('keeps a hadith with unknown grade', () => {
      expect(
        matchesFacets(result({ grade: null }), { ...NO_FACETS, gradings: ['Sahih'] }),
      ).toBe(true)
    })
  })

  describe('century facet', () => {
    it('matches a narrator in the selected century', () => {
      const r = result({ type: 'narrator', century: 2 })
      expect(matchesFacets(r, { ...NO_FACETS, centuries: [2] })).toBe(true)
      expect(matchesFacets(r, { ...NO_FACETS, centuries: [3] })).toBe(false)
    })

    it('keeps a mid bucket exact — a lone "3rd" must not leak later centuries', () => {
      expect(matchesFacets(result({ type: 'narrator', century: 3 }), { ...NO_FACETS, centuries: [3] })).toBe(true)
      expect(matchesFacets(result({ type: 'narrator', century: 7 }), { ...NO_FACETS, centuries: [3] })).toBe(false)
      expect(matchesFacets(result({ type: 'narrator', century: 4 }), { ...NO_FACETS, centuries: [3] })).toBe(false)
    })

    it('treats only the fixed top bucket as open-ended (5th+)', () => {
      expect(matchesFacets(result({ type: 'narrator', century: 7 }), { ...NO_FACETS, centuries: [5] })).toBe(true)
      expect(matchesFacets(result({ type: 'narrator', century: 4 }), { ...NO_FACETS, centuries: [5] })).toBe(false)
      // a non-top bucket stays exact even when the top bucket is also selected
      expect(matchesFacets(result({ type: 'narrator', century: 2 }), { ...NO_FACETS, centuries: [1, 5] })).toBe(false)
      expect(matchesFacets(result({ type: 'narrator', century: 1 }), { ...NO_FACETS, centuries: [1, 5] })).toBe(true)
    })

    it('keeps a narrator with unknown century and ignores the facet for hadiths', () => {
      expect(matchesFacets(result({ type: 'narrator', century: null }), { ...NO_FACETS, centuries: [2] })).toBe(true)
      expect(matchesFacets(result({ type: 'hadith' }), { ...NO_FACETS, centuries: [2] })).toBe(true)
    })
  })

  describe('topic facet', () => {
    // `topics` holds canonical tokens (the backend maps free-text tags onto the
    // vocabulary); the selection holds the same tokens. (#1061)
    it('matches when a selected canonical token is present', () => {
      const r = result({ type: 'hadith', topics: ['fiqh', 'ibadah'] })
      expect(matchesFacets(r, { ...NO_FACETS, topics: ['fiqh'] })).toBe(true)
    })

    it('drops a hadith with no overlapping canonical topic', () => {
      const r = result({ type: 'hadith', topics: ['fiqh'] })
      expect(matchesFacets(r, { ...NO_FACETS, topics: ['aqidah'] })).toBe(false)
    })

    it('keeps a hadith with no topics under any topic filter (permissive)', () => {
      expect(
        matchesFacets(result({ type: 'hadith', topics: [] }), { ...NO_FACETS, topics: ['aqidah'] }),
      ).toBe(true)
    })

    it('uncategorized selection isolates empty-topic results, dropping categorized ones', () => {
      const empty = result({ type: 'hadith', topics: [] })
      const categorized = result({ type: 'hadith', topics: ['fiqh'] })
      expect(matchesFacets(empty, { ...NO_FACETS, topics: ['uncategorized'] })).toBe(true)
      expect(matchesFacets(categorized, { ...NO_FACETS, topics: ['uncategorized'] })).toBe(false)
    })
  })

  // Regression for #1060: semantic search hits used to carry no facet metadata,
  // so an active facet never excluded them (every hit looked "unknown"). Now that
  // the semantic endpoint projects collection/grade/topics, the same matcher
  // refines semantic results — and the page's score sort preserves cosine order.
  it('refines semantic-style results once they carry facet metadata, preserving rank order', () => {
    const semanticHits: SearchResult[] = [
      result({ id: 's1', type: 'hadith', collection: 'Sahih al-Bukhari', grade: 'sahih', score: 0.93 }),
      result({ id: 's2', type: 'hadith', collection: 'Sahih Muslim', grade: 'sahih', score: 0.88 }),
      result({ id: 's3', type: 'hadith', collection: 'Sahih al-Bukhari', grade: 'daif', score: 0.81 }),
    ]
    const facets: FacetSelection = { ...NO_FACETS, collections: ['Sahih al-Bukhari'] }

    const refined = semanticHits
      .filter((r) => matchesFacets(r, facets))
      .sort((a, b) => b.score - a.score)

    // Only the Bukhari hits survive, still in descending cosine order.
    expect(refined.map((r) => r.id)).toEqual(['s1', 's3'])
  })

  // Regression for #1060 + #1061: the semantic endpoint must canonicalize
  // topic_tags (via canonical_topics_for_tags) so a semantic hit carries the same
  // canonical tokens the topic facet compares against. With RAW tags the topic
  // facet would never match and would wrongly exclude the hit — the no-op #1060
  // fixes, here proven for the topic facet specifically.
  it('refines semantic-style hits by a canonical topic facet, preserving rank order', () => {
    const semanticHits: SearchResult[] = [
      result({ id: 't1', type: 'hadith', topics: ['akhlaq'], score: 0.95 }),
      result({ id: 't2', type: 'hadith', topics: ['fiqh'], score: 0.9 }),
      result({ id: 't3', type: 'hadith', topics: ['akhlaq', 'aqidah'], score: 0.7 }),
    ]
    // The facet selection holds canonical tokens (#1061), the same vocabulary the
    // semantic endpoint now projects onto each hit.
    const facets: FacetSelection = { ...NO_FACETS, topics: ['akhlaq'] }

    const refined = semanticHits
      .filter((r) => matchesFacets(r, facets))
      .sort((a, b) => b.score - a.score)

    // Only the canonical-akhlaq hits survive, still in descending cosine order;
    // the fiqh-only hit is excluded (canonical token mismatch, not permissive).
    expect(refined.map((r) => r.id)).toEqual(['t1', 't3'])
  })

  it('requires all active facet groups to match (AND across groups)', () => {
    const r = result({ type: 'hadith', collection: 'Sahih al-Bukhari', grade: 'sahih', topics: ['fiqh'] })
    expect(
      matchesFacets(r, {
        collections: ['Sahih al-Bukhari'],
        gradings: ['Sahih'],
        centuries: [],
        topics: ['fiqh'],
      }),
    ).toBe(true)
    expect(
      matchesFacets(r, {
        collections: ['Sahih al-Bukhari'],
        gradings: ['Hasan'], // grade mismatch fails the whole result
        centuries: [],
        topics: ['fiqh'],
      }),
    ).toBe(false)
  })
})
