import { describe, it, expect } from 'vitest'

import { DEFAULT_LOCALE, LOCALES, getLocaleDir, isSupportedLocale } from '../config'
import ar from '../locales/ar.json'
import bs from '../locales/bs.json'
import en from '../locales/en.json'
import id from '../locales/id.json'
import ms from '../locales/ms.json'
import tr from '../locales/tr.json'
import ur from '../locales/ur.json'

const BUNDLES: Record<string, unknown> = { en, tr, id, ms, ar, bs, ur }

// CLDR plural-category suffixes appended to a base key by i18next. Two locales
// can legitimately differ in which of these exist, so parity is checked on the
// suffix-stripped base key.
const PLURAL_SUFFIX = /_(zero|one|two|few|many|other)$/

function flattenKeys(obj: unknown, prefix = ''): string[] {
  if (obj === null || typeof obj !== 'object') return [prefix]
  return Object.entries(obj as Record<string, unknown>).flatMap(([k, v]) =>
    flattenKeys(v, prefix ? `${prefix}.${k}` : k),
  )
}

function baseKeySet(bundle: unknown): Set<string> {
  return new Set(flattenKeys(bundle).map((k) => k.replace(PLURAL_SUFFIX, '')))
}

describe('locale bundles', () => {
  const enKeys = baseKeySet(en)

  it('ships a bundle for every configured locale', () => {
    for (const { code } of LOCALES) {
      expect(BUNDLES[code], `missing bundle for ${code}`).toBeDefined()
    }
  })

  it.each(LOCALES.map((l) => l.code))('locale %s has the same base keys as English', (code) => {
    const keys = baseKeySet(BUNDLES[code])
    const missing = [...enKeys].filter((k) => !keys.has(k))
    const extra = [...keys].filter((k) => !enKeys.has(k))
    expect({ code, missing, extra }).toEqual({ code, missing: [], extra: [] })
  })

  it.each(LOCALES.map((l) => l.code))('locale %s has no empty strings', (code) => {
    const empties = flattenKeys(BUNDLES[code]).filter((path) => {
      const value = path
        .split('.')
        .reduce<unknown>((acc, part) => (acc as Record<string, unknown>)?.[part], BUNDLES[code])
      return typeof value === 'string' && value.trim() === ''
    })
    expect(empties).toEqual([])
  })
})

describe('locale config', () => {
  it('includes exactly the six toggleable locales plus English', () => {
    expect(LOCALES.map((l) => l.code).sort()).toEqual(['ar', 'bs', 'en', 'id', 'ms', 'tr', 'ur'])
  })

  it('uses unique locale codes', () => {
    const codes = LOCALES.map((l) => l.code)
    expect(new Set(codes).size).toBe(codes.length)
  })

  it('marks Arabic and Urdu as RTL and the rest as LTR', () => {
    const rtl = LOCALES.filter((l) => l.dir === 'rtl').map((l) => l.code)
    expect(rtl.sort()).toEqual(['ar', 'ur'])
  })

  it('defaults to English (LTR)', () => {
    expect(DEFAULT_LOCALE).toBe('en')
    expect(getLocaleDir(DEFAULT_LOCALE)).toBe('ltr')
  })

  it('getLocaleDir falls back to ltr for unknown codes', () => {
    expect(getLocaleDir('xx')).toBe('ltr')
  })

  it('isSupportedLocale narrows known codes only', () => {
    expect(isSupportedLocale('ar')).toBe(true)
    expect(isSupportedLocale('xx')).toBe(false)
    expect(isSupportedLocale(null)).toBe(false)
  })
})
