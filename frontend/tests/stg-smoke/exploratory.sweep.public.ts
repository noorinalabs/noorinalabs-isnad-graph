/**
 * Exploratory sweep — PUBLIC (anonymous) surface (#969).
 *
 * Walks every unauthenticated route with NO storage-state, cataloging
 * load/console/network status per route. Runs in the `sweep-public` project of
 * `playwright.stg.config.ts`; needs no creds, so it always runs.
 *
 * This is the cataloging counterpart to `login.public.spec.ts` (which asserts a
 * few load-bearing invariants). The sweep instead records the full picture into
 * `sweep-results/records/` for `aggregate.ts` to turn into the coverage report.
 */
import { test } from '@playwright/test'
import { PUBLIC_ROUTES } from './sweep/routes'
import { softAssert, visitAndCatalog } from './sweep/catalog'

test.describe('exploratory sweep: public surface', () => {
  for (const route of PUBLIC_ROUTES) {
    test(`${route.label} [${route.path}]`, async ({ page }) => {
      const result = await visitAndCatalog(page, route)
      softAssert(result)
    })
  }
})
