import { test, expect, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const authUser = JSON.parse(readFileSync(join(__dirname, 'fixtures/auth-user.json'), 'utf-8'))
const narrators = JSON.parse(readFileSync(join(__dirname, 'fixtures/narrators.json'), 'utf-8'))

async function mockAuthAndData(page: Page) {
  // Mock auth — return authenticated user
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(authUser) }),
  )

  // Catch-all for API requests to prevent hangs
  await page.route('**/api/v1/**', (route) => {
    const url = route.request().url()

    if (url.includes('/narrators')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(narrators) })
    }
    if (url.includes('/collections')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, page: 1, limit: 20 }),
      })
    }
    if (url.includes('/hadiths/facets')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ collections: [], grades: [], corpora: [] }),
      })
    }
    if (url.includes('/hadiths')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, page: 1, limit: 20 }),
      })
    }
    if (url.includes('/timeline/range')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ min_year: 1, max_year: 500 }),
      })
    }
    if (url.includes('/timeline')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ narrators: [] }),
      })
    }
    if (url.includes('/search')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: [], total: 0 }),
      })
    }
    if (url.includes('/auth/me')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(authUser) })
    }

    // Default: return empty 200 for any unmatched API call
    return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
  })

  // Set auth token so ProtectedRoute sees it
  await page.addInitScript(() => {
    localStorage.setItem('access_token', 'mock-token')
  })
}

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthAndData(page)
  })

  test('home page loads for authenticated user', async ({ page }) => {
    await page.goto('/')

    const nav = page.getByRole('navigation', { name: 'Main navigation' })
    await expect(nav).toBeVisible()
  })

  test('navigates to Narrators page', async ({ page }) => {
    await page.goto('/')
    const nav = page.getByRole('navigation', { name: 'Main navigation' })

    await nav.getByRole('link', { name: 'Narrators' }).click()
    await expect(page).toHaveURL(/\/narrators/)
  })

  test('navigates to Hadiths page', async ({ page }) => {
    await page.goto('/')
    const nav = page.getByRole('navigation', { name: 'Main navigation' })

    await nav.getByRole('link', { name: 'Hadiths' }).click()
    await expect(page).toHaveURL(/\/hadiths/)
  })

  test('navigates to Collections page', async ({ page }) => {
    await page.goto('/')
    const nav = page.getByRole('navigation', { name: 'Main navigation' })

    await nav.getByRole('link', { name: 'Collections' }).click()
    await expect(page).toHaveURL(/\/collections/)
  })

  test('navigates to Search page', async ({ page }) => {
    await page.goto('/')
    const nav = page.getByRole('navigation', { name: 'Main navigation' })

    await nav.getByRole('link', { name: 'Search' }).click()
    await expect(page).toHaveURL(/\/search/)
  })

  test('navigates to Timeline page', async ({ page }) => {
    await page.goto('/')
    const nav = page.getByRole('navigation', { name: 'Main navigation' })

    await nav.getByRole('link', { name: 'Timeline' }).click()
    await expect(page).toHaveURL(/\/timeline/)
  })

  test('sidebar shows user name and sign out button', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByText('Test User')).toBeVisible()
    await expect(page.getByRole('button', { name: /sign out/i })).toBeVisible()
  })
})
