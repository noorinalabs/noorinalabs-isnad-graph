/**
 * Authenticated smoke — ADMIN audit surface (#1140 regression guard, ig#1146).
 *
 * Runs with the storage-state seeded by `auth.setup.ts`. Self-skips unless the
 * provisioned smoke account is admin-capable (STG_SMOKE_ADMIN=1) — see
 * `requireAdmin()`. When active it asserts the load-bearing invariant that
 * #1140 regressed: `/admin/audit` renders the audit log THROUGH the
 * user-service `audit_log` chain (audit-log relocation to user-service
 * Postgres, noorinalabs-main#…), rather than 500-ing or bouncing.
 *
 * Two legs, both gate-grade:
 *   1. UI:  the AuditLogPage mounts its heading + table shell (data OR the
 *           empty-state row) and shows NO `.error-text` — i.e. `fetchAuditLogs`
 *           resolved instead of throwing.
 *   2. API: `GET /api/v1/admin/audit` returns 200 (not 500) — the isnad-graph
 *           admin route → user-service audit_log chain is healthy.
 */
import { test, expect } from '@playwright/test'
import { requireAdmin } from './helpers'

test.describe('authenticated smoke: admin audit surface (#1140 guard)', () => {
  test.beforeEach(() => requireAdmin())

  test('/admin/audit renders the audit log (no redirect, no error state)', async ({ page }) => {
    await page.goto('/admin/audit', { waitUntil: 'networkidle' })

    // AdminLayout bounces a non-admin to '/'; assert we stayed on the route.
    await expect(page).not.toHaveURL(/\/login/)
    await expect(page).toHaveURL(/\/admin\/audit/)

    // The page shell mounted.
    await expect(page.getByRole('heading', { name: 'Audit Log' })).toBeVisible()

    // The table renders once the query resolves (data rows or the
    // "No audit entries found." empty-state row — both prove a 200 response).
    await expect(page.locator('table.data-table')).toBeVisible()

    // The AuditLogPage renders `.error-text` when the audit_log chain errors —
    // its absence is the #1140 regression guard.
    await expect(page.locator('.error-text')).toHaveCount(0)
  })

  test('GET /api/v1/admin/audit returns 200 (audit_log chain healthy, not 500)', async ({
    page,
  }) => {
    // Pull the JWT the setup project seeded so the API call is authenticated;
    // page.request shares cookies but not localStorage.
    await page.goto('/', { waitUntil: 'commit' })
    const token = await page.evaluate(() => localStorage.getItem('access_token'))
    expect(token, 'no access_token in storage-state — auth setup did not seed it').toBeTruthy()

    const res = await page.request.get('/api/v1/admin/audit?page=1&limit=20', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(
      res.status(),
      `admin audit returned ${res.status()} — body: ${(await res.text()).slice(0, 200)}`,
    ).toBe(200)
  })
})
