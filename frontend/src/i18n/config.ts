// i18n locale configuration — the single source of truth for which UI languages
// are supported, how they render, and how the preference is persisted.
//
// SCOPE: this powers translation of UI chrome only (navigation, buttons, labels,
// error pages). Scholarly source data (hadith text, narrator names, collection
// names) comes from the API and is rendered as-is — it is never routed through
// i18next. See issue #703.

export type Direction = 'ltr' | 'rtl'

export interface LocaleMeta {
  /** BCP-47 / ISO-639-1 code used as the i18next language key. */
  code: string
  /** English name of the language (for documentation / fallback labels). */
  name: string
  /** Native endonym shown in the language switcher. */
  nativeName: string
  /** Text direction — drives the `dir` attribute on <html> for RTL locales. */
  dir: Direction
}

/**
 * Supported UI locales. English is the default + fallback; the other six are the
 * toggleable locales requested in #703. Arabic and Urdu are right-to-left.
 */
export const LOCALES: readonly LocaleMeta[] = [
  { code: 'en', name: 'English', nativeName: 'English', dir: 'ltr' },
  { code: 'tr', name: 'Turkish', nativeName: 'Türkçe', dir: 'ltr' },
  { code: 'id', name: 'Indonesian', nativeName: 'Bahasa Indonesia', dir: 'ltr' },
  { code: 'ms', name: 'Malay', nativeName: 'Bahasa Melayu', dir: 'ltr' },
  { code: 'ar', name: 'Arabic', nativeName: 'العربية', dir: 'rtl' },
  { code: 'bs', name: 'Bosnian', nativeName: 'Bosanski', dir: 'ltr' },
  { code: 'ur', name: 'Urdu', nativeName: 'اردو', dir: 'rtl' },
] as const

export type LocaleCode = (typeof LOCALES)[number]['code']

/** Default + fallback locale. */
export const DEFAULT_LOCALE: LocaleCode = 'en'

/** localStorage key holding the persisted locale preference. */
export const STORAGE_KEY = 'isnad-graph-locale'

const LOCALE_BY_CODE = new Map(LOCALES.map((l) => [l.code, l]))

/** Type guard: is the given string one of our supported locale codes? */
export function isSupportedLocale(code: string | null | undefined): code is LocaleCode {
  return typeof code === 'string' && LOCALE_BY_CODE.has(code)
}

/** Text direction for a locale code; falls back to `ltr` for unknown codes. */
export function getLocaleDir(code: string): Direction {
  return LOCALE_BY_CODE.get(code)?.dir ?? 'ltr'
}

/** Metadata for a locale code, or `undefined` if unsupported. */
export function getLocaleMeta(code: string): LocaleMeta | undefined {
  return LOCALE_BY_CODE.get(code)
}
