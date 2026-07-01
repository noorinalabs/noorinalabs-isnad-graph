import { describe, it, expect } from 'vitest'

import en from '../../../i18n/locales/en.json'

// Durable gate for the ig#1104 raw-key-leak class (Nneka, PR#1160): the locale
// key-parity gate compares locales *to each other*, so a key that a page calls
// but that is missing from ALL 7 bundles equally slips through — and with
// `returnNull: false` the page then renders the raw dotted path. That is
// exactly how `admin.moderation.*` shipped un-added on ModerationPage.
//
// This asserts the opposite invariant, statically from source: every `admin.*`
// key literal referenced anywhere in an admin/* PAGE source must resolve in the
// English fallback bundle (`fallbackLng: 'en'`). It scans string literals, so it
// catches both direct `t('admin.x')` calls and indirected keys (e.g. the
// DashboardPage `labelKey: 'admin.dashboard.obsGrafanaLabel'` observability
// links passed through `t(labelKey)`).

// Vite raw-imports the admin page sources at collect time (browser-native, no
// node fs). `../*.tsx` matches the page files under src/pages/admin/, not the
// __tests__ subdirectory.
const PAGE_SOURCES = import.meta.glob('../*.tsx', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const CLDR_CATEGORIES = ['zero', 'one', 'two', 'few', 'many', 'other']

function flattenKeys(obj: unknown, prefix = ''): string[] {
  if (obj === null || typeof obj !== 'object') return [prefix]
  return Object.entries(obj as Record<string, unknown>).flatMap(([k, v]) =>
    flattenKeys(v, prefix ? `${prefix}.${k}` : k),
  )
}

const EN_KEYS = new Set(flattenKeys(en))

// A referenced key resolves if it exists verbatim OR as a count-plural base key
// whose CLDR variants (`_one`/`_other`/…) exist — i18next selects those at
// runtime from the numeric `count` option.
function resolves(key: string): boolean {
  if (EN_KEYS.has(key)) return true
  return CLDR_CATEGORIES.some((c) => EN_KEYS.has(`${key}_${c}`))
}

function referencedAdminKeys(): Map<string, string[]> {
  const re = /['"](admin\.[A-Za-z0-9_.]+)['"]/g
  const byKey = new Map<string, string[]>()
  for (const [path, src] of Object.entries(PAGE_SOURCES)) {
    const file = path.split('/').pop() ?? path
    for (const m of src.matchAll(re)) {
      const key = m[1]
      if (!key) continue
      const files = byKey.get(key) ?? []
      if (!files.includes(file)) files.push(file)
      byKey.set(key, files)
    }
  }
  return byKey
}

describe('admin/* page i18n keys resolve in the en bundle (ig#1104)', () => {
  const referenced = referencedAdminKeys()

  it('finds admin.* key references to check (guards against a no-op scan)', () => {
    expect(referenced.size).toBeGreaterThan(50)
  })

  it('every referenced admin.* key resolves in en (no raw-key leak)', () => {
    const unresolved = [...referenced.entries()]
      .filter(([key]) => !resolves(key))
      .map(([key, files]) => `${key} (used in: ${files.join(', ')})`)
    expect(unresolved).toEqual([])
  })
})
