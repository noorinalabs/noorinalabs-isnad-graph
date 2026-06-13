/**
 * Route inventory for the exploratory sweep (#969).
 *
 * Single source of truth for the app surface the sweep walks. Mirrors the
 * router in `src/App.tsx` (kept in lock-step — when a route is added/removed
 * there, update here). Each entry declares:
 *
 *   - `path`     — the URL path to visit (concrete, with a representative id
 *                  substituted for `:param` routes so detail pages exercise a
 *                  real lookup rather than a router 404).
 *   - `label`    — human-readable name used in the catalog + report.
 *   - `area`     — the owning surface (drives bucket-issue triage / grouping).
 *   - `access`   — who can reach it: `public` (no auth), `auth` (protected),
 *                  `admin` (admin-role gated). Drives which sweep spec runs it.
 *   - `landmark` — an optional accessible-role probe asserted as a "did the
 *                  page actually render its shell?" signal. Absent ⇒ the sweep
 *                  records load/console/network status only (no shell probe).
 *   - `interactions` — optional notes on the primary interaction(s) the sweep
 *                  attempts (search, expand, select…). Recorded in the catalog
 *                  so the coverage report states what was exercised vs merely
 *                  loaded.
 *
 * Detail-route ids are deliberately env-overridable: real staging ids differ
 * from any fixture, and a wrong id turns a "page broken" finding into a false
 * positive. Override via SWEEP_NARRATOR_ID / SWEEP_HADITH_ID / SWEEP_COLLECTION_ID
 * when a known-good id for the target environment is available.
 */

export type Access = 'public' | 'auth' | 'admin'

export interface RouteProbe {
  /** Accessible role to probe (e.g. 'heading', 'navigation', 'img'). */
  role: string
  /** Optional accessible name (regex source or exact string). */
  name?: string
}

export interface SweepRoute {
  path: string
  label: string
  area: string
  access: Access
  landmark?: RouteProbe
  interactions?: string
}

/** Representative detail-route ids — override per environment via env vars. */
const NARRATOR_ID = process.env.SWEEP_NARRATOR_ID ?? 'narrator-001'
const HADITH_ID = process.env.SWEEP_HADITH_ID ?? 'bukhari:1'
const COLLECTION_ID = process.env.SWEEP_COLLECTION_ID ?? 'bukhari'

/**
 * Public routes — reachable without a session. Exercised anonymously by
 * `exploratory.sweep.public.ts`.
 */
export const PUBLIC_ROUTES: SweepRoute[] = [
  {
    path: '/login',
    label: 'Login',
    area: 'auth',
    access: 'public',
    landmark: { role: 'heading', name: 'Isnad Graph' },
    interactions: 'provider buttons present; email/password form present',
  },
  {
    path: '/pricing',
    label: 'Pricing',
    area: 'billing',
    access: 'public',
    interactions: 'plan tiers render',
  },
  {
    path: '/check-email',
    label: 'Check Email',
    area: 'auth',
    access: 'public',
  },
  {
    path: '/verify',
    label: 'Verify Email',
    area: 'auth',
    access: 'public',
  },
  {
    path: '/trial-expired',
    label: 'Trial Expired',
    area: 'billing',
    access: 'public',
  },
  {
    // A route that does not exist — confirms the SPA renders a real 404 page
    // rather than a blank screen or an uncaught error.
    path: '/this-route-does-not-exist',
    label: 'Not Found (404 fallback)',
    area: 'routing',
    access: 'public',
    landmark: { role: 'heading' },
  },
]

/**
 * Authenticated routes — require a live session. Exercised by
 * `exploratory.sweep.auth.spec.ts` (self-skips without stg creds).
 */
export const AUTH_ROUTES: SweepRoute[] = [
  {
    path: '/',
    label: 'Home',
    area: 'core',
    access: 'auth',
    landmark: { role: 'navigation' },
  },
  {
    path: '/narrators',
    label: 'Narrators',
    area: 'narrators',
    access: 'auth',
    landmark: { role: 'heading', name: 'Narrators' },
    interactions: 'list renders; result rows / empty-state visible',
  },
  {
    path: `/narrators/${NARRATOR_ID}`,
    label: 'Narrator detail',
    area: 'narrators',
    access: 'auth',
    interactions: 'bio, activity timeline, transmission network for one narrator',
  },
  {
    path: '/hadiths',
    label: 'Hadiths',
    area: 'hadiths',
    access: 'auth',
    landmark: { role: 'heading', name: 'Hadiths' },
    interactions: 'list renders; facets / empty-state visible',
  },
  {
    path: `/hadiths/${HADITH_ID}`,
    label: 'Hadith detail',
    area: 'hadiths',
    access: 'auth',
    interactions: 'matn, isnad, parallels for one hadith',
  },
  {
    path: '/collections',
    label: 'Collections',
    area: 'collections',
    access: 'auth',
    landmark: { role: 'heading' },
  },
  {
    path: `/collections/${COLLECTION_ID}`,
    label: 'Collection detail',
    area: 'collections',
    access: 'auth',
  },
  {
    path: '/search',
    label: 'Search',
    area: 'search',
    access: 'auth',
    landmark: { role: 'heading' },
    interactions: 'query input present; submit a representative query',
  },
  {
    path: '/timeline',
    label: 'Timeline',
    area: 'timeline',
    access: 'auth',
    landmark: { role: 'heading' },
    interactions: 'historical-events overlay / activity timeline renders',
  },
  {
    path: '/compare',
    label: 'Compare (Browse Parallels)',
    area: 'compare',
    access: 'auth',
    landmark: { role: 'heading' },
    interactions: 'parallels search + comparison surface',
  },
  {
    path: '/graph',
    label: 'Graph Explorer',
    area: 'graph',
    access: 'auth',
    landmark: { role: 'img', name: 'Narrator transmission network graph' },
    interactions: 'narrator search input + force-graph canvas mount',
  },
  {
    path: '/profile',
    label: 'Profile / Account',
    area: 'account',
    access: 'auth',
    landmark: { role: 'heading' },
    interactions: 'display-name edit, preferences (results-per-page, language, theme), sessions',
  },
]

/**
 * Admin routes — require admin role. Exercised by the auth sweep too, but
 * recorded under their own area; a non-admin test user records these as
 * `forbidden` (a valid outcome, not a gap).
 */
export const ADMIN_ROUTES: SweepRoute[] = [
  { path: '/admin/dashboard', label: 'Admin · Dashboard', area: 'admin', access: 'admin' },
  { path: '/admin/users', label: 'Admin · User management', area: 'admin', access: 'admin' },
  { path: '/admin/health', label: 'Admin · System health', area: 'admin', access: 'admin' },
  { path: '/admin/stats', label: 'Admin · Content stats', area: 'admin', access: 'admin' },
  { path: '/admin/data', label: 'Admin · Data management', area: 'admin', access: 'admin' },
  { path: '/admin/analytics', label: 'Admin · Usage analytics', area: 'admin', access: 'admin' },
  { path: '/admin/moderation', label: 'Admin · Moderation', area: 'admin', access: 'admin' },
  { path: '/admin/reports', label: 'Admin · Reports', area: 'admin', access: 'admin' },
  { path: '/admin/config', label: 'Admin · Config', area: 'admin', access: 'admin' },
  { path: '/admin/audit', label: 'Admin · Audit log', area: 'admin', access: 'admin' },
  { path: '/admin/reset', label: 'Admin · Pipeline reset', area: 'admin', access: 'admin' },
]

/** Every authenticated-context route (protected + admin). */
export const ALL_AUTH_ROUTES: SweepRoute[] = [...AUTH_ROUTES, ...ADMIN_ROUTES]
