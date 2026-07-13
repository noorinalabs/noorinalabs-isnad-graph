import { describe, it, expect } from 'vitest'

import {
  TABAQA_ORDER,
  UNKNOWN_TABAQA,
  normalizeTabaqa,
  computeTabaqaLayers,
  tabaqaRankByNode,
} from '../tabaqa'
import type { GraphNode } from '../../types/api'

function node(overrides: Partial<GraphNode> = {}): GraphNode {
  return {
    id: 'n',
    label: 'N',
    name_ar: 'ن',
    name_en: 'N',
    type: 'narrator',
    generation: null,
    community_id: null,
    in_degree: 0,
    out_degree: 0,
    betweenness_centrality: null,
    pagerank: null,
    sect_affiliation: null,
    trustworthiness_consensus: null,
    death_year_ah: null,
    birth_year_ah: null,
    kunya: null,
    nisba: null,
    over_merged: false,
    over_merge_note: null,
    ...overrides,
  }
}

describe('normalizeTabaqa', () => {
  it('maps the canonical backend enum values to themselves', () => {
    expect(normalizeTabaqa('sahabi')).toBe('sahabi')
    expect(normalizeTabaqa('tabii')).toBe('tabii')
    expect(normalizeTabaqa('taba_tabii')).toBe('taba_tabii')
    expect(normalizeTabaqa('atba_taba_tabiin')).toBe('atba_taba_tabiin')
    expect(normalizeTabaqa('later')).toBe('later')
  })

  it('is case- and punctuation-insensitive across spelling variants', () => {
    expect(normalizeTabaqa('Companion')).toBe('sahabi')
    expect(normalizeTabaqa('Companions')).toBe('sahabi')
    expect(normalizeTabaqa('Successor')).toBe('tabii')
    // The corpus carries "tabi_tabiin" as well as the enum's "taba_tabii".
    expect(normalizeTabaqa('tabi_tabiin')).toBe('taba_tabii')
  })

  it('returns null for missing or unmapped generations', () => {
    expect(normalizeTabaqa(null)).toBeNull()
    expect(normalizeTabaqa(undefined)).toBeNull()
    expect(normalizeTabaqa('')).toBeNull()
    expect(normalizeTabaqa('unknown')).toBeNull()
    expect(normalizeTabaqa('some-uncatalogued-value')).toBeNull()
  })
})

describe('computeTabaqaLayers', () => {
  it('orders bands by canonical generation, earliest first', () => {
    const layers = computeTabaqaLayers([
      node({ id: 'a', generation: 'later' }),
      node({ id: 'b', generation: 'sahabi' }),
      node({ id: 'c', generation: 'tabii' }),
    ])
    expect(layers.map((l) => l.key)).toEqual(['sahabi', 'tabii', 'later'])
    // Ranks are contiguous and reflect chronological order.
    expect(layers.map((l) => l.rank)).toEqual([0, 1, 2])
  })

  it('only emits bands that actually contain nodes (contiguous ranks)', () => {
    const layers = computeTabaqaLayers([
      node({ id: 'a', generation: 'sahabi' }),
      node({ id: 'b', generation: 'later' }),
    ])
    // The intermediate generations with no nodes are skipped, not left as gaps.
    expect(layers.map((l) => l.key)).toEqual(['sahabi', 'later'])
    expect(layers.map((l) => l.rank)).toEqual([0, 1])
  })

  it('collects unknown/unmapped generations into a trailing band', () => {
    const layers = computeTabaqaLayers([
      node({ id: 'known', generation: 'sahabi' }),
      node({ id: 'missing', generation: null }),
      node({ id: 'weird', generation: 'not-a-real-tabaqa' }),
    ])
    const last = layers[layers.length - 1]!
    expect(last.key).toBe(UNKNOWN_TABAQA)
    expect(last.rank).toBe(layers.length - 1)
    // Both the null and the unmapped node fall into the unknown band.
    expect(new Set(last.nodeIds)).toEqual(new Set(['missing', 'weird']))
  })

  it('places the unknown band last even when its nodes appear first', () => {
    const layers = computeTabaqaLayers([
      node({ id: 'missing', generation: null }),
      node({ id: 'known', generation: 'tabii' }),
    ])
    expect(layers.map((l) => l.key)).toEqual(['tabii', UNKNOWN_TABAQA])
  })

  it('orders nodes within a band chronologically by death year (undated last)', () => {
    const layers = computeTabaqaLayers([
      node({ id: 'undated', generation: 'sahabi', death_year_ah: null }),
      node({ id: 'late', generation: 'sahabi', death_year_ah: 78 }),
      node({ id: 'early', generation: 'sahabi', death_year_ah: 32 }),
    ])
    expect(layers).toHaveLength(1)
    expect(layers[0]!.nodeIds).toEqual(['early', 'late', 'undated'])
  })

  it('returns no bands for an empty node set', () => {
    expect(computeTabaqaLayers([])).toEqual([])
  })
})

describe('tabaqaRankByNode', () => {
  it('maps every node id to its band rank', () => {
    const layers = computeTabaqaLayers([
      node({ id: 'a', generation: 'sahabi' }),
      node({ id: 'b', generation: 'tabii' }),
      node({ id: 'c', generation: null }),
    ])
    const ranks = tabaqaRankByNode(layers)
    expect(ranks.get('a')).toBe(0)
    expect(ranks.get('b')).toBe(1)
    expect(ranks.get('c')).toBe(2)
    expect(ranks.size).toBe(3)
  })
})

describe('TABAQA_ORDER', () => {
  it('matches the backend NarratorGeneration enum ordering (excluding unknown)', () => {
    expect([...TABAQA_ORDER]).toEqual([
      'sahabi',
      'tabii',
      'taba_tabii',
      'atba_taba_tabiin',
      'later',
    ])
  })
})
