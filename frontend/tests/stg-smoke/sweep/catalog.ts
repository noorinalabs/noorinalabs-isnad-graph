/**
 * Catalog plumbing for the exploratory sweep (#969).
 *
 * The sweep's job is to WALK the app surface and EMIT a machine-readable
 * catalog of what works vs what's missing/broken — not to gate a build. So the
 * per-route checks are deliberately SOFT (`expect.soft`): a broken route is
 * recorded and shows up red in the Playwright report, but it does not abort the
 * walk, so one bad page never hides the state of the rest.
 *
 * ### Why per-route files instead of one shared catalog
 *
 * Playwright runs tests across parallel workers in separate processes. A single
 * shared `catalog.json` mutated by every test would race. Instead each route
 * visit writes ONE self-contained record to `sweep-results/records/<slug>.json`,
 * and `aggregate.ts` (run after the sweep) folds them into `sweep-catalog.json`
 * plus a human-readable `SWEEP-CATALOG.md`. Append-only, race-free.
 */
import { expect, type Page, type Response } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { SweepRoute } from './routes'

const here = dirname(fileURLToPath(import.meta.url))

/** Output roots — gitignored; consumed by `aggregate.ts` and CI artifact upload. */
export const RESULTS_DIR = join(here, '..', '..', '..', 'sweep-results')
export const RECORDS_DIR = join(RESULTS_DIR, 'records')
export const SHOTS_DIR = join(RESULTS_DIR, 'screenshots')

/** Coarse outcome classification surfaced in the coverage report. */
export type Outcome =
  | 'ok' // loaded, landmark present (if probed), no console/network errors
  | 'ok-with-warnings' // loaded + landmark, but console and/or non-fatal network errors
  | 'redirected-to-login' // protected route bounced — session not honored
  | 'forbidden' // admin route refused for a non-admin user (valid, not a gap)
  | 'landmark-missing' // page loaded but its expected shell did not render
  | 'load-error' // navigation threw / never settled
  | 'empty-state' // loaded but shows a "no data" empty state (candidate data gap)

export interface RouteResult {
  path: string
  label: string
  area: string
  access: SweepRoute['access']
  outcome: Outcome
  finalUrl: string
  landmarkProbed: boolean
  landmarkVisible: boolean | null
  emptyStateText: string | null
  consoleErrors: string[]
  /** Responses with status >= 400 observed while the route loaded. */
  networkErrors: { url: string; status: number }[]
  /** Requests that failed at the transport layer (DNS, refused, aborted). */
  requestFailures: { url: string; reason: string }[]
  pageErrors: string[]
  interactions: string | null
  screenshot: string | null
  timestamp: string
}

function slugify(path: string): string {
  return path.replace(/^\//, '').replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_|_$/g, '') || 'root'
}

/** Best-effort empty-state heuristic — matches the app's "no X yet/found" copy. */
const EMPTY_STATE_RE = /no\s+[\w\s-]*?(found|yet|available|results|data|events)/i

/**
 * Visit one route, collect console/network/page diagnostics, probe the optional
 * landmark, screenshot, classify, and persist the record. SOFT throughout — a
 * gap is data, not a thrown error.
 */
export async function visitAndCatalog(page: Page, route: SweepRoute): Promise<RouteResult> {
  mkdirSync(RECORDS_DIR, { recursive: true })
  mkdirSync(SHOTS_DIR, { recursive: true })

  const consoleErrors: string[] = []
  const networkErrors: RouteResult['networkErrors'] = []
  const requestFailures: RouteResult['requestFailures'] = []
  const pageErrors: string[] = []

  const onConsole = (msg: { type(): string; text(): string }): void => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  }
  const onResponse = (res: Response): void => {
    const status = res.status()
    if (status >= 400) networkErrors.push({ url: res.url(), status })
  }
  const onRequestFailed = (req: {
    url(): string
    failure(): { errorText: string } | null
  }): void => {
    requestFailures.push({ url: req.url(), reason: req.failure()?.errorText ?? 'unknown' })
  }
  const onPageError = (err: Error): void => {
    pageErrors.push(err.message)
  }

  page.on('console', onConsole)
  page.on('response', onResponse)
  page.on('requestfailed', onRequestFailed)
  page.on('pageerror', onPageError)

  let loadError: string | null = null
  try {
    await page.goto(route.path, { waitUntil: 'networkidle', timeout: 45_000 })
  } catch (err) {
    loadError = err instanceof Error ? err.message : String(err)
  }

  const finalUrl = page.url()
  const redirectedToLogin = /\/login(\?|$)/.test(finalUrl)
  const forbidden = /\/forbidden(\?|$)/.test(finalUrl)

  // Landmark probe (soft) — did the page render its expected shell?
  let landmarkVisible: boolean | null = null
  if (route.landmark && !loadError && !redirectedToLogin && !forbidden) {
    const { role, name } = route.landmark
    const locator = name
      ? page.getByRole(role as Parameters<Page['getByRole']>[0], {
          name: new RegExp(name, 'i'),
        })
      : page.getByRole(role as Parameters<Page['getByRole']>[0])
    landmarkVisible = await locator
      .first()
      .isVisible()
      .catch(() => false)
  }

  // Empty-state heuristic.
  let emptyStateText: string | null = null
  if (!loadError && !redirectedToLogin && !forbidden) {
    const bodyText = await page.locator('body').innerText().catch(() => '')
    const m = bodyText.match(EMPTY_STATE_RE)
    emptyStateText = m ? m[0] : null
  }

  // Screenshot (best-effort; full page).
  const slug = `${route.access}__${slugify(route.path)}`
  const shotPath = join(SHOTS_DIR, `${slug}.png`)
  let screenshot: string | null = null
  try {
    await page.screenshot({ path: shotPath, fullPage: true })
    screenshot = shotPath
  } catch {
    screenshot = null
  }

  page.off('console', onConsole)
  page.off('response', onResponse)
  page.off('requestfailed', onRequestFailed)
  page.off('pageerror', onPageError)

  const outcome: Outcome = classify({
    access: route.access,
    loadError,
    redirectedToLogin,
    forbidden,
    landmarkProbed: Boolean(route.landmark),
    landmarkVisible,
    emptyStateText,
    consoleErrors,
    networkErrors,
  })

  const result: RouteResult = {
    path: route.path,
    label: route.label,
    area: route.area,
    access: route.access,
    outcome,
    finalUrl,
    landmarkProbed: Boolean(route.landmark),
    landmarkVisible,
    emptyStateText,
    consoleErrors,
    networkErrors,
    requestFailures,
    pageErrors,
    interactions: route.interactions ?? null,
    screenshot,
    timestamp: new Date().toISOString(),
  }

  writeFileSync(join(RECORDS_DIR, `${slug}.json`), JSON.stringify(result, null, 2))
  return result
}

function classify(args: {
  access: SweepRoute['access']
  loadError: string | null
  redirectedToLogin: boolean
  forbidden: boolean
  landmarkProbed: boolean
  landmarkVisible: boolean | null
  emptyStateText: string | null
  consoleErrors: string[]
  networkErrors: { url: string; status: number }[]
}): Outcome {
  if (args.loadError) return 'load-error'
  // An admin route bounced for a non-admin user is a valid auth outcome.
  if (args.forbidden) return 'forbidden'
  // A protected route bouncing to /login means the session was not honored.
  if (args.redirectedToLogin && args.access !== 'public') return 'redirected-to-login'
  if (args.landmarkProbed && args.landmarkVisible === false) return 'landmark-missing'
  if (args.emptyStateText) return 'empty-state'
  if (args.consoleErrors.length > 0 || args.networkErrors.length > 0) return 'ok-with-warnings'
  return 'ok'
}

/**
 * Soft-assert the result so the Playwright report shows red for a gap WITHOUT
 * aborting the sweep. The catalog is the source of truth; these soft checks
 * just make the HTML report skimmable.
 */
export function softAssert(result: RouteResult): void {
  // Forbidden on an admin route (non-admin test user) is acceptable.
  if (result.outcome === 'forbidden') return
  expect.soft(result.outcome, `${result.label} (${result.path}) → ${result.outcome}`).not.toBe(
    'load-error',
  )
  expect
    .soft(result.outcome, `${result.label} (${result.path}) bounced to /login`)
    .not.toBe('redirected-to-login')
  expect
    .soft(
      result.outcome,
      `${result.label} (${result.path}) shell did not render its landmark`,
    )
    .not.toBe('landmark-missing')
  expect
    .soft(
      result.pageErrors,
      `${result.label} (${result.path}) uncaught page errors: ${result.pageErrors.join(' | ')}`,
    )
    .toHaveLength(0)
}
