import { test, expect, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const authUser = JSON.parse(readFileSync(join(__dirname, 'fixtures/auth-user.json'), 'utf-8'))
const searchResults = JSON.parse(readFileSync(join(__dirname, 'fixtures/search-results.json'), 'utf-8'))

async function mockAuth(page: Page) {
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(authUser) }),
  )
  await page.addInitScript(() => {
    localStorage.setItem('access_token', 'mock-token')
  })
}

test.describe('Search', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuth(page)
  })

  test('search input is present on the search page', async ({ page }) => {
    await page.goto('/search')

    const input = page.getByRole('combobox')
    await expect(input).toBeVisible()
    await expect(input).toHaveAttribute('placeholder', /search hadith/i)
  })

  test('typeahead dropdown appears when typing', async ({ page }) => {
    // Mock search results for typeahead
    await page.route('**/api/v1/search?*', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(searchResults),
      }),
    )

    await page.goto('/search')

    const input = page.getByRole('combobox')
    await input.fill('Abu')

    // Wait for typeahead listbox to appear
    const listbox = page.getByRole('listbox')
    await expect(listbox).toBeVisible()

    // Should contain grouped results
    await expect(listbox.getByText('Narrators')).toBeVisible()
    await expect(listbox.getByText('Abu Hurayra')).toBeVisible()
  })

  test('search results render on submit', async ({ page }) => {
    await page.route('**/api/v1/search?*', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(searchResults),
      }),
    )

    await page.goto('/search')

    const input = page.getByRole('combobox')
    await input.fill('Abu Hurayra')
    await page.getByRole('button', { name: 'Search', exact: true }).click()

    // Results should appear
    await expect(page.getByText(/showing 3 results/i)).toBeVisible()

    // Verify result cards rendered (use article role to target result cards specifically)
    const resultCards = page.getByRole('article')
    await expect(resultCards).toHaveCount(3)
    await expect(page.getByText('Actions are judged by intentions')).toBeVisible()
    await expect(page.getByText('Sahih al-Bukhari')).toBeVisible()
  })

  test('suggested queries are shown when no query is entered', async ({ page }) => {
    await page.goto('/search')

    await expect(page.getByText('Search the hadith corpus')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Abu Hurayra' })).toBeVisible()
  })
})
