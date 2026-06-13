/**
 * Exploratory sweep — AUTHENTICATED + ADMIN surface (#969).
 *
 * Walks every protected and admin route with the JWT seeded by `auth.setup.ts`,
 * cataloging load/console/network/empty-state status per route. Runs in the
 * `sweep-auth` project of `playwright.stg.config.ts` (depends on `setup`,
 * reuses its storage-state). Self-skips when stg creds are absent so a
 * credential-less context stays green.
 *
 * Admin routes record `forbidden` (not a gap) when the test user lacks the
 * admin role — provision an admin test user to exercise the admin surface.
 */
import { test } from '@playwright/test'
import { requireAuth } from './helpers'
import { ALL_AUTH_ROUTES } from './sweep/routes'
import { softAssert, visitAndCatalog } from './sweep/catalog'

test.describe('exploratory sweep: authenticated + admin surface', () => {
  test.beforeEach(() => requireAuth())

  for (const route of ALL_AUTH_ROUTES) {
    test(`${route.label} [${route.path}]`, async ({ page }) => {
      const result = await visitAndCatalog(page, route)
      softAssert(result)
    })
  }
})
