/**
 * Session-expired modal E2E — #1027
 * ---------------------------------
 * Regression test for the session-expired modal blowing out past the browser
 * width. Root cause: the design-system Dialog's positioning/sizing utilities
 * (`start-1/2`, `-translate-x/y-1/2`, `max-w-lg`, …) are referenced only inside
 * the compiled DS bundle, which the app's Tailwind content scan does not crawl,
 * so they produced no CSS and the modal rendered unconstrained. The fix
 * force-generates that utility set via `@source inline(...)` in
 * `src/styles/theme.css`.
 *
 * These assertions verify the *rendered* result (the only place the bug is
 * observable): the dialog is width-constrained well below the viewport, is
 * horizontally centered, and never introduces a horizontal page scrollbar — at
 * both a narrow (mobile) and a wide (desktop) viewport.
 *
 * Like the other specs here, the backend is mocked at the route layer — only the
 * built frontend on `baseURL` (vite preview) is required.
 */
import { test, expect, type Page } from '@playwright/test'

const authUser = {
  id: 'test-user-001',
  email: 'test@example.com',
  name: 'Test User',
  is_admin: false,
  provider: 'email',
  email_verified: true,
  roles: ['reader'],
}

async function mockAuth(page: Page) {
  // Identity endpoint — makes AuthProvider set `user`, which is the precondition
  // for the session-expired event to surface the modal.
  await page.route('**/api/v1/users/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(authUser),
    }),
  )
  // Everything else returns empty 200 so unscoped queries don't hang.
  await page.route('**/api/v1/**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
  )
  await page.addInitScript(() => {
    localStorage.setItem('access_token', 'mock-token')
  })
}

// Surface the modal by emitting the same event the API clients fire on a
// genuinely-expired session. Dispatched in a poll because the handler is a no-op
// until `user` has loaded; re-dispatching is harmless.
async function openSessionExpiredModal(page: Page) {
  const title = page.getByText('Session expired', { exact: true })
  await expect
    .poll(
      async () => {
        await page.evaluate(() =>
          window.dispatchEvent(new Event('auth:session-expired')),
        )
        return title.isVisible().catch(() => false)
      },
      { timeout: 8000 },
    )
    .toBe(true)
}

const VIEWPORTS = [
  { name: 'mobile', width: 375, height: 720 },
  { name: 'desktop', width: 1280, height: 800 },
]

for (const vp of VIEWPORTS) {
  test(`session-expired modal is width-constrained and centered (${vp.name})`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height })
    await mockAuth(page)
    await page.goto('/narrators')

    await openSessionExpiredModal(page)

    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()

    const box = await dialog.boundingBox()
    expect(box).not.toBeNull()
    if (!box) return

    // 1. Width-constrained: never wider than the viewport, and capped near the
    //    DS `max-w-lg` (32rem ≈ 512px) on wide screens (pre-fix it spanned the
    //    full viewport width).
    expect(box.width).toBeLessThanOrEqual(vp.width)
    expect(box.width).toBeLessThanOrEqual(560)

    // 2. Horizontally centered (within a small tolerance).
    const boxCenter = box.x + box.width / 2
    expect(Math.abs(boxCenter - vp.width / 2)).toBeLessThanOrEqual(24)

    // 3. No horizontal page overflow — the core "blows out browser width" bug.
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    )
    expect(overflow).toBeLessThanOrEqual(1)
  })
}
