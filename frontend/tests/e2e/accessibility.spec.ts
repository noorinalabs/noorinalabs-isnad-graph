import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const authUser = JSON.parse(readFileSync(join(__dirname, 'fixtures/auth-user.json'), 'utf-8'))

test.describe('Accessibility', () => {
  test('login page has no accessibility violations', async ({ page }) => {
    await page.goto('/login')

    // Wait for the page to be fully rendered
    await expect(page.getByRole('heading', { name: 'Isnad Graph' })).toBeVisible()

    const results = await new AxeBuilder({ page })
      .disableRules(['color-contrast', 'landmark-one-main', 'region'])
      .analyze()

    expect(results.violations).toEqual([])
  })

  test('home page (authenticated) has no accessibility violations', async ({ page }) => {
    // Mock auth
    await page.route('**/api/v1/auth/me', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(authUser) }),
    )
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'mock-token')
    })

    await page.goto('/')

    // Wait for the nav to render (proves auth loaded)
    await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeVisible()

    const results = await new AxeBuilder({ page })
      .disableRules(['color-contrast'])
      .analyze()

    expect(results.violations).toEqual([])
  })
})
