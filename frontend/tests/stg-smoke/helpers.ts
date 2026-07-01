/**
 * Shared helpers for the stg smoke specs (#968).
 */
import { test, type Page } from '@playwright/test'
import { hasAuthCreds, SMOKE_ADMIN } from './env'

/**
 * Skip the current authenticated spec when no stg creds are provisioned.
 * Call at the top of every `*.auth.spec.ts` test (or describe) so the suite
 * stays green in a credential-less context.
 */
export function requireAuth(): void {
  test.skip(!hasAuthCreds, 'stg creds not configured (STG_TEST_EMAIL / STG_TEST_PASSWORD)')
}

/**
 * Skip the current admin spec unless the provisioned smoke account is
 * admin-capable (ig#1146). Requires creds AND STG_SMOKE_ADMIN=1 — the latter is
 * the owner's signal that the smoke email has been granted the `admin` role
 * (see README.md § Admin smoke account). Without it an admin route would 403 /
 * bounce, so we self-skip rather than manufacture a red until the cross-repo
 * admin seed is provisioned.
 */
export function requireAdmin(): void {
  requireAuth()
  test.skip(
    !SMOKE_ADMIN,
    'smoke account is not admin-capable — set STG_SMOKE_ADMIN=1 once the smoke ' +
      'email has been granted the admin role (see README.md § Admin smoke account, ig#1146)',
  )
}

/** True if a response body looks like an SPA HTML document rather than an asset. */
export function looksLikeHtml(body: string): boolean {
  const head = body.trimStart().slice(0, 200).toLowerCase()
  return head.startsWith('<!doctype html') || head.startsWith('<html')
}

/**
 * Attach a page-error collector. Returns a getter for any uncaught page
 * errors observed since attach — used to guard against the prod-login
 * `JSON.parse` crash (noorinalabs-main#637).
 */
export function collectPageErrors(page: Page): () => string[] {
  const errors: string[] = []
  page.on('pageerror', (err) => errors.push(err.message))
  return () => errors
}
