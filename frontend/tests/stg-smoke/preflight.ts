/**
 * Pre-flight config validation for the stg smoke auth setup (ig#1146).
 *
 * Pure and node-free by design, so it is unit-testable under vitest
 * (`src/__tests__/stgSmokePreflight.test.ts`) WITHOUT a live stg env — CI proves
 * the loud-fail mechanic on every PR even though the smoke suite itself only
 * runs on dispatch/schedule against the deployed app.
 *
 * The problem this guards (ig#1146): the harness previously *silently skipped*
 * the authenticated leg whenever STG_TEST_EMAIL / STG_TEST_PASSWORD were absent.
 * In a context that is supposed to have secrets (the scheduled/dispatched CI
 * run) that silent skip made an UNWIRED / MISCONFIGURED harness read GREEN — the
 * exact false-confidence this issue removes. When `requireAuth` is set
 * (STG_REQUIRE_AUTH=1, which the e2e-stg-smoke workflow sets), missing creds now
 * throw so the run reads RED, not green.
 */

/** Resolved harness configuration handed to the pre-flight evaluator. */
export interface HarnessAuthConfig {
  /** Frontend origin under test (STG_BASE_URL / PROD_BASE_URL, with defaults). */
  baseUrl: string
  /** user-service origin that issues JWTs (USER_SERVICE_URL, with defaults). */
  userServiceUrl: string
  /** STG_TEST_EMAIL (may be empty when unprovisioned). */
  email: string
  /** STG_TEST_PASSWORD (may be empty when unprovisioned). */
  password: string
  /** When true, absent creds are a hard error (RED) instead of a soft skip. */
  requireAuth: boolean
}

/**
 * What the auth-setup project should do next:
 *   - `login` — creds present, proceed with the programmatic login;
 *   - `skip`  — creds absent AND not required, soft-skip (local public-only run).
 * A state that must read RED throws {@link HarnessConfigError} instead.
 */
export type PreflightDecision =
  | { action: 'login' }
  | { action: 'skip'; reason: string }

/** A harness-configuration error that must fail the setup loudly (non-zero / RED). */
export class HarnessConfigError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'HarnessConfigError'
  }
}

/**
 * Decide what the auth-setup should do, or throw for a state that must read RED:
 *   - empty base URL or user-service URL → always fatal (no origin to test);
 *   - creds absent AND `requireAuth`     → fatal (unwired harness in a context
 *     that is supposed to carry secrets);
 *   - creds absent AND !`requireAuth`    → soft skip (local public-only run);
 *   - creds present                      → login.
 */
export function evaluateAuthPreflight(cfg: HarnessAuthConfig): PreflightDecision {
  const missingUrls: string[] = []
  if (!cfg.baseUrl.trim()) missingUrls.push('STG_BASE_URL (frontend origin)')
  if (!cfg.userServiceUrl.trim()) missingUrls.push('USER_SERVICE_URL (JWT issuer)')
  if (missingUrls.length > 0) {
    throw new HarnessConfigError(
      `stg smoke harness misconfigured — empty ${missingUrls.join(' and ')}. ` +
        'These have built-in vhost defaults; an empty value means a repo var was ' +
        'set to "". Provision the correct URL(s) or unset the var. (ig#1146)',
    )
  }

  const hasCreds = Boolean(cfg.email.trim() && cfg.password.trim())
  if (hasCreds) return { action: 'login' }

  if (cfg.requireAuth) {
    throw new HarnessConfigError(
      'stg smoke authenticated leg REQUIRED but credentials are missing: provision ' +
        'the STG_TEST_EMAIL and STG_TEST_PASSWORD repo secrets (owner-provisioned). ' +
        'This run has STG_REQUIRE_AUTH=1, so an unwired harness fails LOUD (RED) ' +
        'instead of silently skipping the authenticated leg. (ig#1146)',
    )
  }

  return {
    action: 'skip',
    reason:
      'stg creds not configured (STG_TEST_EMAIL / STG_TEST_PASSWORD) and ' +
      'STG_REQUIRE_AUTH not set — authenticated leg soft-skipped (local public-only run).',
  }
}
