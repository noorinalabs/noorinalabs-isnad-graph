/**
 * Golden-path E2E tests — #907
 * ----------------------------
 * These specs cover the three user journeys that #907 calls out:
 *   1. Login → land in app → click a narrator card → land on detail page
 *   2. Hadith list → click → hadith detail page
 *   3. Admin moderation flow (admin user → /admin/moderation)
 *
 * All API calls are mocked at the route layer (see existing `navigation.spec.ts`
 * precedent). These specs DO NOT require a running Neo4j/Postgres/Redis stack —
 * only the built frontend served on `baseURL` (Playwright config defaults to
 * `http://localhost:4173`, i.e. `vite preview`).
 *
 * Run locally:
 *   cd frontend
 *   npm run build              # produces dist/
 *   npx vite preview --port 4173 &
 *   npm run e2e -- golden-paths
 *
 * Run in CI: see frontend/CI documentation; these specs are co-located with
 * existing E2E specs and run via the same `npm run e2e` command.
 */
import { test, expect, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))

const authUser = JSON.parse(
  readFileSync(join(__dirname, 'fixtures/auth-user.json'), 'utf-8'),
)
const adminUser = JSON.parse(
  readFileSync(join(__dirname, 'fixtures/admin-user.json'), 'utf-8'),
)
const narrators = JSON.parse(
  readFileSync(join(__dirname, 'fixtures/narrators.json'), 'utf-8'),
)
const hadiths = JSON.parse(
  readFileSync(join(__dirname, 'fixtures/hadiths.json'), 'utf-8'),
)
const hadithDetail = JSON.parse(
  readFileSync(join(__dirname, 'fixtures/hadith-detail.json'), 'utf-8'),
)
const dashboardStats = JSON.parse(
  readFileSync(join(__dirname, 'fixtures/dashboard-stats.json'), 'utf-8'),
)
const moderationItems = JSON.parse(
  readFileSync(join(__dirname, 'fixtures/moderation-items.json'), 'utf-8'),
)

type RoleConfig = { admin: boolean }

async function mockBackend(page: Page, config: RoleConfig = { admin: false }) {
  const user = config.admin ? adminUser : authUser

  // /users/me — primary identity endpoint
  await page.route('**/api/v1/users/me', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(user) }),
  )
  // Legacy alias still hit by some E2E specs
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(user) }),
  )
  await page.route('**/api/v1/auth/subscription', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'trial', tier: 'trial', days_remaining: 7 }),
    }),
  )

  // Narrator detail
  await page.route('**/api/v1/narrators/narrator-001', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(narrators.items[0]),
    }),
  )
  await page.route('**/api/v1/narrators/narrator-001/chains', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ narrator_id: 'narrator-001', chains: [], total: 0 }),
    }),
  )

  // Hadith list + detail
  await page.route('**/api/v1/hadiths/facets**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ source_corpus: ['Sahih al-Bukhari'] }),
    }),
  )
  await page.route('**/api/v1/hadiths/bukhari:1/parallels**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ hadith_id: 'bukhari:1', parallels: [], total: 0 }),
    }),
  )
  await page.route('**/api/v1/hadiths/bukhari:1', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(hadithDetail),
    }),
  )
  await page.route('**/api/v1/hadiths**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(hadiths),
    }),
  )

  // Narrators list
  await page.route('**/api/v1/narrators**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(narrators),
    }),
  )

  // Admin dashboard user counts now come from the user-service stats endpoint
  // (ig#1051) — the isnad-graph dashboard stub was removed.
  await page.route('**/api/v1/users/stats', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(dashboardStats),
    }),
  )
  await page.route('**/api/v1/admin/moderation**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(moderationItems),
    }),
  )

  // Catch-all — return empty 200 so unscoped queries don't hang
  await page.route('**/api/v1/**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
  )

  // Seed auth token so ProtectedRoute sees an authenticated user
  await page.addInitScript(() => {
    localStorage.setItem('access_token', 'mock-token')
  })
}

test.describe('Golden path: narrator list → detail', () => {
  test('clicking a narrator on the Narrators page lands on its detail page', async ({ page }) => {
    await mockBackend(page)
    await page.goto('/narrators')

    // Narrator card for Abu Hurayra is rendered from the fixture
    const card = page.getByText('Abu Hurayra').first()
    await expect(card).toBeVisible()
    await card.click()

    await expect(page).toHaveURL(/\/narrators\/narrator-001/)
  })
})

test.describe('Golden path: hadith list → detail', () => {
  test('clicking a hadith on the Hadiths page lands on its detail page', async ({ page }) => {
    await mockBackend(page)
    await page.goto('/hadiths')

    // Either the Arabic matn or the corpus is enough to identify the row
    const row = page.getByText('Actions are but by intentions').first()
    await expect(row).toBeVisible()
    await row.click()

    await expect(page).toHaveURL(/\/hadiths\/bukhari:1/)
    await expect(
      page.getByRole('heading', { name: /Bukhari 1/ }),
    ).toBeVisible()
  })

  test('hadith detail page renders Arabic matn, English matn, and grade badge', async ({ page }) => {
    await mockBackend(page)
    await page.goto('/hadiths/bukhari:1')

    await expect(page.getByText('إنما الأعمال بالنيات')).toBeVisible()
    await expect(
      page.getByText('Actions are but by intentions'),
    ).toBeVisible()
    await expect(page.getByText('Sahih').first()).toBeVisible()
  })
})

test.describe('Golden path: admin moderation flow', () => {
  test('admin user can land on /admin/moderation', async ({ page }) => {
    await mockBackend(page, { admin: true })
    await page.goto('/admin/moderation')

    // Verify we did NOT bounce to the 403 page (the AdminRoute fallback)
    await expect(page.getByRole('heading', { name: '403' })).toHaveCount(0)
    // Some indicator of the moderation page surface — accept any heading containing "Moderation"
    await expect(page.getByText(/Moderation/i).first()).toBeVisible()
  })

  test('non-admin user is blocked from /admin/moderation with a 403', async ({ page }) => {
    await mockBackend(page, { admin: false })
    await page.goto('/admin/moderation')

    await expect(page.getByRole('heading', { name: '403' })).toBeVisible()
    await expect(
      page.getByText(/You do not have permission/i),
    ).toBeVisible()
  })

  test('admin dashboard renders StatCards from user-service /users/stats', async ({ page }) => {
    await mockBackend(page, { admin: true })
    await page.goto('/admin/dashboard')

    await expect(page.getByRole('heading', { name: 'Admin Dashboard' })).toBeVisible()
    await expect(page.getByText('Total Users')).toBeVisible()
    await expect(page.getByText('42')).toBeVisible()
    await expect(page.getByText('Active Sessions')).toBeVisible()
    await expect(page.getByText('12')).toBeVisible()
  })
})
