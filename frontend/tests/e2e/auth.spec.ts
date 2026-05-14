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

test.describe('OAuth callback redirect', () => {
  // The backend (user-service AUTH_OAUTH_POST_LOGIN_URL) emits a provider-less
  // `/auth/callback?token=...` redirect. These tests guard that the frontend
  // route matches that exact path shape — see issue #824.

  test('success redirect stores token and lands on return URL', async ({ page }) => {
    await page.route('**/api/v1/users/me', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: '1', email: 'test@example.com', name: 'Test User', roles: [] }),
      }),
    )
    await page.route('**/api/v1/subscriptions/me', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ tier: 'trial', status: 'trial', days_remaining: 7 }),
      }),
    )
    await page.route('**/api/v1/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
    )

    await page.goto('/auth/callback?token=oauth-access-token&is_new_user=0&needs_verification=0')

    // Route matched (no fall-through to 404) and AuthCallbackPage navigated away.
    await expect(page).not.toHaveURL(/\/auth\/callback/)
    await expect(page).not.toHaveURL(/\/login/)

    const token = await page.evaluate(() => localStorage.getItem('access_token'))
    expect(token).toBe('oauth-access-token')
  })

  test('new-user redirect lands on email verification', async ({ page }) => {
    await page.route('**/api/v1/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
    )

    await page.goto('/auth/callback?token=oauth-access-token&is_new_user=1&needs_verification=1')

    await expect(page).toHaveURL(/\/check-email/)
  })

  test('error param renders the sign-in failed UI', async ({ page }) => {
    await page.goto('/auth/callback?error=oauth_exchange_failed')

    // Route matched and AuthCallbackPage rendered the error branch rather than
    // navigating away. (toBeAttached, not toBeVisible — the error card's width
    // utilities collapse under the preview build's Tailwind output.)
    await expect(page.getByRole('heading', { name: 'Sign-in failed' })).toBeAttached()
    await expect(
      page.getByText(/unable to complete sign-in with the provider/i),
    ).toBeAttached()
    await expect(page).toHaveURL(/\/auth\/callback/)
  })
})
