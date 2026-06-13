/**
 * Authenticated smoke — protected routes + API status against the live env (#968).
 *
 * Runs with the storage-state seeded by `auth.setup.ts` (JWT in localStorage),
 * so `ProtectedRoute` sees an authenticated user and does NOT bounce to /login.
 * Self-skips when stg creds are absent (see requireAuth()).
 *
 * Asserts the load-bearing invariants the P4W2 live sweep found broken:
 *   - key pages (home, narrators, hadiths) render their shell, not a redirect
 *   - the graph explorer mounts its canvas surface
 *   - `/api/v1/search` returns 200 for a representative query (not 500/422)
 */
import { test, expect } from '@playwright/test'
import { requireAuth } from './helpers'

test.describe('authenticated smoke: protected pages', () => {
  test.beforeEach(() => requireAuth())

  test('home does not redirect to /login (auth session is live)', async ({ page }) => {
    await page.goto('/', { waitUntil: 'networkidle' })
    await expect(page).not.toHaveURL(/\/login/)
    // Main app chrome renders for an authenticated user.
    await expect(page.getByRole('navigation').first()).toBeVisible()
  })

  test('narrators page renders its heading', async ({ page }) => {
    await page.goto('/narrators', { waitUntil: 'networkidle' })
    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.getByRole('heading', { name: 'Narrators' })).toBeVisible()
  })

  test('hadiths page renders its heading', async ({ page }) => {
    await page.goto('/hadiths', { waitUntil: 'networkidle' })
    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.getByRole('heading', { name: 'Hadiths' })).toBeVisible()
  })

  test('graph explorer mounts its canvas surface', async ({ page }) => {
    await page.goto('/graph', { waitUntil: 'networkidle' })
    await expect(page).not.toHaveURL(/\/login/)
    // The explorer shell is present regardless of how much data staging holds:
    // the narrator search input + the graph canvas region both render.
    await expect(page.getByPlaceholder('Search narrator...')).toBeVisible()
    await expect(
      page.getByRole('img', { name: 'Narrator transmission network graph' }),
    ).toBeVisible()
  })
})

test.describe('authenticated smoke: search API status', () => {
  test.beforeEach(() => requireAuth())

  test('/api/v1/search returns 200 (not 500/422) for a representative query', async ({ page }) => {
    // Pull the JWT the setup project seeded so the API call is authenticated;
    // page.request shares the browser context (cookies) but not localStorage.
    await page.goto('/', { waitUntil: 'commit' })
    const token = await page.evaluate(() => localStorage.getItem('access_token'))
    expect(token, 'no access_token in storage-state — auth setup did not seed it').toBeTruthy()

    const res = await page.request.get('/api/v1/search?q=iman&limit=5', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(
      res.status(),
      `search returned ${res.status()} — body: ${(await res.text()).slice(0, 200)}`,
    ).toBe(200)
  })
})
