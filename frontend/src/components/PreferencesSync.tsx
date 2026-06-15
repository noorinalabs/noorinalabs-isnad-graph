import { useProfilePreferenceSync } from '../hooks/useProfilePreferenceSync'

/**
 * Headless component: on login it hydrates the live theme + UI locale from the
 * authenticated user's server-stored preferences (#1044). Renders nothing; it
 * exists only to host the sync effect inside the Auth/Theme/Query providers.
 */
export default function PreferencesSync() {
  useProfilePreferenceSync()
  return null
}
