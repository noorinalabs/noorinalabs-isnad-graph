// i18next bootstrap for the UI. Imported once from `main.tsx` (and from the test
// setup) so the singleton is initialised before any component renders.
//
// Resources are bundled statically (no async backend) — the translation set is
// small UI-chrome only, so eager-loading all locales keeps the language switch
// instantaneous and avoids a loading flash. See issue #703.

import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import {
  DEFAULT_LOCALE,
  LOCALES,
  STORAGE_KEY,
  getLocaleDir,
  isSupportedLocale,
} from './config'
import ar from './locales/ar.json'
import bs from './locales/bs.json'
import en from './locales/en.json'
import id from './locales/id.json'
import ms from './locales/ms.json'
import tr from './locales/tr.json'
import ur from './locales/ur.json'

const resources = {
  en: { translation: en },
  tr: { translation: tr },
  id: { translation: id },
  ms: { translation: ms },
  ar: { translation: ar },
  bs: { translation: bs },
  ur: { translation: ur },
}

/** Read the persisted locale, falling back to the default. */
function detectInitialLocale(): string {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (isSupportedLocale(stored)) return stored
  } catch {
    // localStorage can throw in private-mode / SSR — fall through to default.
  }
  return DEFAULT_LOCALE
}

/**
 * Reflect the active locale onto the document root: the `lang` attribute for
 * accessibility/SEO and the `dir` attribute so the whole layout mirrors for RTL
 * locales (Arabic, Urdu). Safe to call when `document` is undefined.
 */
export function applyDocumentLocale(locale: string): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.setAttribute('lang', locale)
  root.setAttribute('dir', getLocaleDir(locale))
}

const initialLocale = detectInitialLocale()

void i18n.use(initReactI18next).init({
  resources,
  lng: initialLocale,
  fallbackLng: DEFAULT_LOCALE,
  supportedLngs: LOCALES.map((l) => l.code),
  // Keys are namespaced via dot-paths inside a single `translation` namespace.
  interpolation: {
    escapeValue: false, // React already escapes interpolated values.
  },
  returnNull: false,
})

// Keep the document direction/lang and the persisted preference in sync whenever
// the language changes at runtime.
i18n.on('languageChanged', (lng) => {
  applyDocumentLocale(lng)
  try {
    localStorage.setItem(STORAGE_KEY, lng)
  } catch {
    // Persisting is best-effort; ignore storage failures.
  }
})

// Apply once for the initial render (the event above only fires on changes).
applyDocumentLocale(initialLocale)

export default i18n
