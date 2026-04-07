import { test, expect } from '@playwright/test'

test.describe('Authentication', () => {
  test('login page renders with heading and description', async ({ page }) => {
    await page.goto('/login')

    await expect(page.getByRole('heading', { name: 'Isnad Graph' })).toBeVisible()
    await expect(page.getByText('Sign in to access the hadith analysis platform')).toBeVisible()
  })

  test('OAuth buttons are present', async ({ page }) => {
    await page.goto('/login')

    await expect(page.getByRole('button', { name: /sign in with google/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /sign in with github/i })).toBeVisible()
  })

  test('email sign-in form is visible by default', async ({ page }) => {
    await page.goto('/login')

    await expect(page.getByLabel('Email')).toBeVisible()
    await expect(page.getByLabel('Password')).toBeVisible()
    await expect(page.getByRole('button', { name: /sign in$/i })).toBeVisible()
  })

  test('register tab shows additional fields', async ({ page }) => {
    await page.goto('/login')

    await page.getByRole('tab', { name: /create account/i }).click()

    await expect(page.getByLabel('Name')).toBeVisible()
    await expect(page.getByLabel('Confirm password')).toBeVisible()
  })

  test('redirects to login when unauthenticated', async ({ page }) => {
    // No auth mock — accessing protected route should redirect to /login
    await page.goto('/')

    await expect(page).toHaveURL(/\/login/)
  })

  test('redirects to login when accessing protected narrators route', async ({ page }) => {
    await page.goto('/narrators')

    await expect(page).toHaveURL(/\/login/)
  })
})
