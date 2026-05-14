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

test.describe('OAuth callback redirect contract', () => {
  // Regression guard for the cross-repo OAuth callback contract (#890, see #824).
  // user-service `_build_post_login_url()` ALWAYS appends `/{provider}`, so the
  // real redirect is `/auth/callback/google?token=...` — WITH the provider
  // segment. These tests goto the provider-qualified URL so they fail if the
  // frontend route `auth/callback/:provider` is ever changed to drop `:provider`
  // (which would make React Router 404 the real redirect — that was #824).

  test('provider-qualified success redirect matches the route and stores token', async ({
    page,
  }) => {
    await page.route('**/api/v1/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
    )

    await page.goto('/auth/callback/google?token=oauth-access-token&is_new_user=0&needs_verification=0')

    // Route matched (no fall-through to the `*` 404 catch-all) and
    // AuthCallbackPage navigated away after processing the token.
    await expect(page).not.toHaveURL(/\/auth\/callback/)
    await expect(page).not.toHaveURL(/\/login/)

    const token = await page.evaluate(() => localStorage.getItem('access_token'))
    expect(token).toBe('oauth-access-token')
  })

  test('fragment-delivered token is parsed and stored (prep for user-service #68)', async ({
    page,
  }) => {
    await page.route('**/api/v1/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
    )

    // user-service #68 moves the token from the query string into the URL
    // fragment (`#token=...`) so it never reaches server logs / Referer.
    // Non-secret params (is_new_user/needs_verification) stay in the query.
    await page.goto(
      '/auth/callback/google?is_new_user=0&needs_verification=0#token=fragment-access-token',
    )

    await expect(page).not.toHaveURL(/\/auth\/callback/)
    await expect(page).not.toHaveURL(/\/login/)

    const token = await page.evaluate(() => localStorage.getItem('access_token'))
    expect(token).toBe('fragment-access-token')
  })

  test('provider-qualified new-user redirect lands on email verification', async ({ page }) => {
    await page.route('**/api/v1/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
    )

    await page.goto('/auth/callback/google?token=oauth-access-token&is_new_user=1&needs_verification=1')

    await expect(page).toHaveURL(/\/check-email/)
  })

  test('provider-qualified error redirect renders the sign-in failed UI', async ({ page }) => {
    await page.goto('/auth/callback/google?error=oauth_exchange_failed')

    // Route matched and AuthCallbackPage rendered the error branch rather than
    // navigating away. (toBeAttached, not toBeVisible — the error card's width
    // utilities collapse under the preview build's Tailwind output; tracked
    // separately in #889.)
    await expect(page.getByRole('heading', { name: 'Sign-in failed' })).toBeAttached()
    await expect(
      page.getByText(/unable to complete sign-in with the provider/i),
    ).toBeAttached()
    await expect(page).toHaveURL(/\/auth\/callback\/google/)
  })
})
