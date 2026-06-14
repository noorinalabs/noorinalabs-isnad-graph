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

    it('treats the largest selected bucket as open-ended (5th+)', () => {
      expect(matchesFacets(result({ type: 'narrator', century: 7 }), { ...NO_FACETS, centuries: [5] })).toBe(true)
      expect(matchesFacets(result({ type: 'narrator', century: 4 }), { ...NO_FACETS, centuries: [5] })).toBe(false)
      // a non-max bucket stays exact even when a higher bucket is also selected
      expect(matchesFacets(result({ type: 'narrator', century: 2 }), { ...NO_FACETS, centuries: [1, 5] })).toBe(false)
      expect(matchesFacets(result({ type: 'narrator', century: 1 }), { ...NO_FACETS, centuries: [1, 5] })).toBe(true)
    })

    it('keeps a narrator with unknown century and ignores the facet for hadiths', () => {
      expect(matchesFacets(result({ type: 'narrator', century: null }), { ...NO_FACETS, centuries: [2] })).toBe(true)
      expect(matchesFacets(result({ type: 'hadith' }), { ...NO_FACETS, centuries: [2] })).toBe(true)
    })
  })

  describe('topic facet', () => {
    it('matches a topic tag against the parenthetical token of the label', () => {
      const r = result({ type: 'hadith', topics: ['fiqh', 'prayer'] })
      expect(matchesFacets(r, { ...NO_FACETS, topics: ['Jurisprudence (fiqh)'] })).toBe(true)
    })

    it('matches a single-word label with no parenthetical', () => {
      const r = result({ type: 'hadith', topics: ['eschatology'] })
      expect(matchesFacets(r, { ...NO_FACETS, topics: ['Eschatology'] })).toBe(true)
    })

    it('drops a hadith with no overlapping topic', () => {
      const r = result({ type: 'hadith', topics: ['inheritance'] })
      expect(matchesFacets(r, { ...NO_FACETS, topics: ['Theology (aqidah)'] })).toBe(false)
    })

    it('keeps a hadith with no topic tags', () => {
      expect(matchesFacets(result({ type: 'hadith', topics: [] }), { ...NO_FACETS, topics: ['Theology (aqidah)'] })).toBe(true)
    })
  })

  it('requires all active facet groups to match (AND across groups)', () => {
    const r = result({ type: 'hadith', collection: 'Sahih al-Bukhari', grade: 'sahih', topics: ['fiqh'] })
    expect(
      matchesFacets(r, {
        collections: ['Sahih al-Bukhari'],
        gradings: ['Sahih'],
        centuries: [],
        topics: ['Jurisprudence (fiqh)'],
      }),
    ).toBe(true)
    expect(
      matchesFacets(r, {
        collections: ['Sahih al-Bukhari'],
        gradings: ['Hasan'], // grade mismatch fails the whole result
        centuries: [],
        topics: ['Jurisprudence (fiqh)'],
      }),
    ).toBe(false)
  })
})
