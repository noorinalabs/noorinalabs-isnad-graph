import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { fetchProfile } from '../api/profile-client'
import { isSupportedLocale } from '../i18n/config'
import { useAuth } from './useAuth'
import { useTheme } from './useTheme'

/**
 * On login, make the server the source of truth for the two cross-device UI
 * preferences — the color theme and the UI locale — by hydrating `useTheme` and
 * i18next from the authenticated user's stored preferences.
 *
 * Anonymous/offline sessions are untouched (`enabled` is gated on `user`): the
 * theme hook and i18n keep using their localStorage values, which also act as
 * the last-writer-wins cache once authenticated.
 *
 * Hydration runs once per authenticated user (keyed on user id). A mid-session
 * change on the Profile page must not be clobbered by a re-render re-applying the
 * now-stale server value; a fresh login (a different id) re-hydrates.
 */
export function useProfilePreferenceSync(): void {
  const { user } = useAuth()
  const { setTheme } = useTheme()
  const { i18n } = useTranslation()
  const hydratedFor = useRef<string | null>(null)

  const { data } = useQuery({
    queryKey: ['profile'],
    queryFn: fetchProfile,
    enabled: Boolean(user),
  })

  useEffect(() => {
    if (!user) {
      // Logged out — let the next login hydrate afresh.
      hydratedFor.current = null
      return
    }
    if (!data || hydratedFor.current === user.id) return
    hydratedFor.current = user.id

    const { theme, language } = data.preferences
    if (theme === 'light' || theme === 'dark' || theme === 'system') {
      setTheme(theme)
    }
    if (typeof language === 'string' && isSupportedLocale(language)) {
      void i18n.changeLanguage(language)
    }
  }, [user, data, setTheme, i18n])
}
