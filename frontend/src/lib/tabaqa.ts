/**
 * Ṭabaqa (generation) layering for the isnad-tree explorer (ig#1043).
 *
 * The graph explorer can arrange narrator nodes into horizontal bands by their
 * ṭabaqa — the generation-class of classical rijāl/ṭabaqāt literature — so the
 * transmission tree reads chronologically top→bottom (earliest generation at the
 * top). The canonical order mirrors the backend `NarratorGeneration` enum
 * (`src/models/enums.py`): sahabi → tabii → taba_tabii → atba_taba_tabiin →
 * later. Narrators whose generation is missing or unmapped are collected into a
 * trailing "unknown" band so every node still renders (graceful degradation).
 *
 * These helpers are pure so the layering logic is unit-testable in isolation of
 * the D3/canvas renderer (which is exercised via Playwright, not Vitest).
 */
import type { GraphNode } from '../types/api'

/**
 * Canonical ṭabaqa ordering, earliest → latest, mirroring the backend
 * `NarratorGeneration` enum. `unknown` is intentionally excluded here — it is
 * appended as a trailing band by {@link computeTabaqaLayers} only when nodes of
 * unknown generation are present.
 */
export const TABAQA_ORDER = [
  'sahabi',
  'tabii',
  'taba_tabii',
  'atba_taba_tabiin',
  'later',
] as const

export type TabaqaKey = (typeof TABAQA_ORDER)[number]
export const UNKNOWN_TABAQA = 'unknown'
export type TabaqaBandKey = TabaqaKey | typeof UNKNOWN_TABAQA

/** i18n label key per band, resolved by the caller via `t(...)`. */
export const TABAQA_LABEL_KEY: Record<TabaqaBandKey, string> = {
  sahabi: 'graph.tabaqaSahabi',
  tabii: 'graph.tabaqaTabii',
  taba_tabii: 'graph.tabaqaTabaTabii',
  atba_taba_tabiin: 'graph.tabaqaAtbaTabaTabiin',
  later: 'graph.tabaqaLater',
  unknown: 'graph.tabaqaUnknown',
}

/**
 * Alias table mapping a normalized generation token (lowercased, non-letters
 * stripped) to its canonical ṭabaqa key. Covers the backend enum values plus the
 * common English/transliteration synonyms that appear in loaded narrator data
 * (e.g. "Companion", "tabi_tabiin"), so layering is robust to the several spellings
 * the corpus carries for the same generation.
 */
const TABAQA_ALIASES: Record<string, TabaqaKey> = {
  // Companions
  sahabi: 'sahabi',
  sahaba: 'sahabi',
  sahabah: 'sahabi',
  companion: 'sahabi',
  companions: 'sahabi',
  // Successors
  tabii: 'tabii',
  tabi: 'tabii',
  tabiin: 'tabii',
  tabiun: 'tabii',
  successor: 'tabii',
  successors: 'tabii',
  // Followers of the Successors (taba' al-tabi'in)
  tabatabii: 'taba_tabii',
  tabatabiin: 'taba_tabii',
  tabitabiin: 'taba_tabii',
  // Later followers (atba' taba' al-tabi'in)
  atbatabatabiin: 'atba_taba_tabiin',
  atbatabatabin: 'atba_taba_tabiin',
  // Later generations
  later: 'later',
}

/**
 * Normalize a raw `generation` string to a canonical ṭabaqa key, or `null` when
 * the value is missing or does not map to a known generation.
 */
export function normalizeTabaqa(generation: string | null | undefined): TabaqaKey | null {
  if (!generation) return null
  const token = generation.toLowerCase().replace(/[^a-z]/g, '')
  if (!token) return null
  return TABAQA_ALIASES[token] ?? null
}

export interface TabaqaLayer {
  /** Canonical band key, or `unknown` for the trailing catch-all band. */
  key: TabaqaBandKey
  /** 0-based vertical row; earliest generation is rank 0, unknown is always last. */
  rank: number
  /** i18n key for the band's display label. */
  labelKey: string
  /** Node ids in the band, ordered chronologically (see {@link sortChronologically}). */
  nodeIds: string[]
}

/**
 * Order nodes within a band chronologically: by death year, then birth year
 * (both AH), with undated narrators last, breaking remaining ties by id for a
 * stable, deterministic layout.
 */
function sortChronologically(nodes: GraphNode[]): string[] {
  return [...nodes]
    .sort((a, b) => {
      const ay = a.death_year_ah ?? a.birth_year_ah ?? Number.POSITIVE_INFINITY
      const by = b.death_year_ah ?? b.birth_year_ah ?? Number.POSITIVE_INFINITY
      if (ay !== by) return ay - by
      return a.id.localeCompare(b.id)
    })
    .map((n) => n.id)
}

/**
 * Group graph nodes into ṭabaqa bands. Only bands that actually contain nodes
 * get a row, so ranks are contiguous (0..n-1). Known generations come first in
 * canonical order; the `unknown` band (missing/unmapped generation) is always
 * placed last so undated/unclassified narrators sit below the chronological tree
 * rather than disrupting it.
 */
export function computeTabaqaLayers(nodes: GraphNode[]): TabaqaLayer[] {
  const buckets = new Map<TabaqaBandKey, GraphNode[]>()
  for (const n of nodes) {
    const key: TabaqaBandKey = normalizeTabaqa(n.generation) ?? UNKNOWN_TABAQA
    const arr = buckets.get(key)
    if (arr) {
      arr.push(n)
    } else {
      buckets.set(key, [n])
    }
  }

  const ordered = ([...TABAQA_ORDER, UNKNOWN_TABAQA] as TabaqaBandKey[]).filter((k) =>
    buckets.has(k),
  )

  return ordered.map((key, rank) => ({
    key,
    rank,
    labelKey: TABAQA_LABEL_KEY[key],
    nodeIds: sortChronologically(buckets.get(key) ?? []),
  }))
}

/**
 * Flatten computed layers into a node-id → band-rank map, used by the renderer to
 * pin each node to its generation band's vertical position.
 */
export function tabaqaRankByNode(layers: TabaqaLayer[]): Map<string, number> {
  const m = new Map<string, number>()
  for (const layer of layers) {
    for (const id of layer.nodeIds) {
      m.set(id, layer.rank)
    }
  }
  return m
}
