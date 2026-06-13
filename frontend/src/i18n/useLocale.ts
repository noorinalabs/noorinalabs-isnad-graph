// Thin, typed wrapper over react-i18next for reading and switching the UI locale.
// Components that only translate strings should use `useTranslation()` directly;
// this hook is for the language switcher and anything that needs the locale list
// or current direction.

import { useTranslation } from 'react-i18next'

import { DEFAULT_LOCALE, LOCALES, getLocaleDir, type Direction, type LocaleCode } from './config'

export interface UseLocaleResult {
  /** The active locale code (resolved through fallbacks). */
  locale: LocaleCode
  /** Text direction of the active locale. */
  dir: Direction
  /** All selectable locales, in display order. */
  locales: typeof LOCALES
  /** Switch the active locale; persistence + `dir` are handled by the i18n bootstrap. */
  setLocale: (code: LocaleCode) => void
}

export function useLocale(): UseLocaleResult {
  const { i18n } = useTranslation()
  const active = (i18n.resolvedLanguage ?? i18n.language ?? DEFAULT_LOCALE) as LocaleCode

  return {
    locale: active,
    dir: getLocaleDir(active),
    locales: LOCALES,
    setLocale: (code: LocaleCode) => {
      void i18n.changeLanguage(code)
    },
  }
}
