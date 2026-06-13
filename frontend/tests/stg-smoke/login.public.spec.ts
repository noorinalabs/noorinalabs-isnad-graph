/**
 * Public (unauthenticated) smoke — login surface + runtime-config (#968).
 *
 * These run with NO storage-state and need no creds, so they stay green in any
 * context. They encode the load-bearing invariants the P4W2 live sweep found
 * broken in prod:
 *   - `/login` renders providers and does NOT throw a `JSON.parse` (guards the
 *     prod-login crash, noorinalabs-main#637 — caused by the SPA serving HTML
 *     where the app expected JSON).
 *   - `/runtime-config.js` must not be SPA HTML masquerading as a 200 script
 *     (the exact prod regression in feedback_prod_frontend_runtime_config_lag).
 */
import { test, expect } from '@playwright/test'
import { collectPageErrors, looksLikeHtml } from './helpers'

test.describe('public smoke: login surface', () => {
  test('login page renders sign-in options without a JSON.parse crash', async ({ page }) => {
    const pageErrors = collectPageErrors(page)

    await page.goto('/login', { waitUntil: 'networkidle' })

    // The app heading proves the SPA mounted rather than erroring to a blank page.
    await expect(page.getByRole('heading', { name: 'Isnad Graph' })).toBeVisible()

    // Sign-in affordances are present: either the provider buttons (from
    // /auth/providers) or the email form. We assert the email form, which is
    // always rendered, plus at least one OAuth provider button.
    await expect(page.getByLabel('Email')).toBeVisible()
    await expect(page.getByLabel('Password')).toBeVisible()
    await expect(
      page.getByRole('button', { name: /sign in with (google|github)/i }).first(),
    ).toBeVisible()

    // #637 guard: no uncaught error (the prod bug surfaced as `JSON.parse`).
    const errs = pageErrors()
    expect(
      errs.filter((m) => /json|parse|unexpected token/i.test(m)),
      `unexpected JSON/parse page errors on /login: ${errs.join(' | ')}`,
    ).toHaveLength(0)
  })

  test('runtime-config.js is a real asset, never SPA HTML masquerading as 200', async ({
    request,
  }) => {
    const res = await request.get('/runtime-config.js')
    const status = res.status()
    const body = await res.text()

    // The regression we guard: a 200 whose body is the SPA index.html — the
    // app then tries to execute/parse HTML as a config script. A legitimate
    // 404 (asset simply not deployed for this build) is acceptable; a
    // 200-with-HTML is not.
    expect(
      !(status === 200 && looksLikeHtml(body)),
      `runtime-config.js returned 200 with SPA HTML (the prod-login regression). First bytes: ${body
        .trimStart()
        .slice(0, 80)}`,
    ).toBeTruthy()
  })
})
