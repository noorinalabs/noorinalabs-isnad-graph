/**
 * Playwright config for the stg-targeted browser-automation smoke harness (#968).
 *
 * Deliberately SEPARATE from the default `playwright.config.ts` (which drives a
 * local `vite preview` with a fully-mocked backend under `tests/e2e/`). This
 * config drives a real deployed environment and authenticates against the live
 * user-service. Run it explicitly:
 *
 *   npm run e2e:stg                 # against staging
 *   TARGET_ENV=prod npm run e2e:stg # against prod (read-only / smoke-only)
 *
 * Projects:
 *   - `setup`        — programmatic login → persisted storage-state (no-op skip
 *                      when stg creds are absent; see tests/stg-smoke/env.ts).
 *   - `smoke-public` — unauthenticated invariants (login page, runtime-config).
 *                      Always runs; needs no creds.
 *   - `smoke-auth`   — protected-route invariants; depends on `setup` and reuses
 *                      its storage-state. Self-skips when creds are absent.
 *   - `sweep-public` — exploratory cataloging walk of the anonymous surface
 *                      (#969). Soft checks; emits sweep-results/ records.
 *   - `sweep-auth`   — exploratory cataloging walk of the protected + admin
 *                      surface (#969); depends on `setup`, self-skips w/o creds.
 *
 * `npm run e2e:stg` runs only the smoke projects (the #968 contract). The
 * heavier exploratory walk runs separately via `npm run e2e:sweep`, then
 * `npm run sweep:report` aggregates the records into SWEEP-CATALOG.md.
 */
import { defineConfig, devices } from '@playwright/test'
import { BASE_URL, STORAGE_STATE } from './tests/stg-smoke/env'

export default defineConfig({
  testDir: './tests/stg-smoke',
  // Real network round-trips against a deployed env — give pages room to load.
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI
    ? [['html', { outputFolder: 'playwright-report-stg', open: 'never' }], ['list']]
    : 'list',
  outputDir: 'test-results-stg',
  use: {
    baseURL: BASE_URL,
    // Capture diagnostics on failure so a red run is actionable from artifacts.
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'setup',
      testMatch: /auth\.setup\.ts/,
    },
    {
      name: 'smoke-public',
      testMatch: /.*\.public\.spec\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'smoke-auth',
      testMatch: /.*\.auth\.spec\.ts/,
      dependencies: ['setup'],
      use: { ...devices['Desktop Chrome'], storageState: STORAGE_STATE },
    },
    {
      name: 'sweep-public',
      testMatch: /.*\.sweep\.public\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'sweep-auth',
      testMatch: /.*\.sweep\.auth\.ts/,
      dependencies: ['setup'],
      use: { ...devices['Desktop Chrome'], storageState: STORAGE_STATE },
    },
  ],
})
