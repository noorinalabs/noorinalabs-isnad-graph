/**
 * Shared environment resolution for the stg-targeted smoke harness (#968).
 *
 * Unlike the mock-based `tests/e2e/` suite — which drives a locally-built
 * `vite preview` with every API call stubbed — this suite drives a REAL
 * deployed environment (staging by default, prod in read-only/smoke-only
 * mode) and authenticates against the live user-service.
 *
 * Everything is sourced from env vars so the same specs run unchanged in
 * local-dev (export the vars), CI (wired from repo secrets/vars), or against
 * prod (`TARGET_ENV=prod`). Credentials are NEVER hardcoded; when they are
 * absent the authenticated leg self-skips (see `hasAuthCreds`).
 */
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))

/** `stg` (default) or `prod`. Prod is treated as read-only / smoke-only. */
export const TARGET_ENV = (process.env.TARGET_ENV ?? 'stg').toLowerCase()

export const IS_PROD = TARGET_ENV === 'prod'

/** Frontend origin under test. */
export const BASE_URL =
  process.env.STG_BASE_URL ??
  (IS_PROD
    ? process.env.PROD_BASE_URL ?? 'https://isnad.noorinalabs.com'
    : 'https://isnad.stg.noorinalabs.com')

/**
 * user-service origin that issues JWTs. Defaults to the `users.{env}` vhost
 * (deploy#220/#245 carve-out). Overridable for envs where the user-service is
 * reachable under a different host.
 */
export const USER_SERVICE_URL =
  process.env.USER_SERVICE_URL ??
  (IS_PROD
    ? process.env.PROD_USER_SERVICE_URL ?? 'https://users.noorinalabs.com'
    : 'https://users.stg.noorinalabs.com')

/** Test-user credentials for the authenticated leg — secrets only, no defaults. */
export const TEST_EMAIL = process.env.STG_TEST_EMAIL ?? ''
export const TEST_PASSWORD = process.env.STG_TEST_PASSWORD ?? ''

/**
 * True only when BOTH credentials are present. Drives the authenticated
 * leg's skip-guard so the public smoke (login page / runtime-config) stays
 * green in a credential-less context while the protected-route checks run
 * wherever real creds are provisioned.
 */
export const hasAuthCreds = Boolean(TEST_EMAIL && TEST_PASSWORD)

/**
 * When true, the auth-setup FAILS LOUD (RED) if creds are missing instead of
 * soft-skipping the authenticated leg (ig#1146). Set STG_REQUIRE_AUTH=1 in any
 * context that is supposed to carry secrets — the `e2e-stg-smoke` workflow does
 * — so an unwired/misconfigured harness can never read green. Left unset (local
 * dev, and the intentionally-soft `e2e-stg-sweep`) preserves the public-only
 * self-skip.
 */
export const REQUIRE_AUTH = /^(1|true|yes)$/i.test(process.env.STG_REQUIRE_AUTH ?? '')

/**
 * True when the provisioned smoke account is admin-capable — the owner sets
 * STG_SMOKE_ADMIN=1 once the smoke email has been granted the `admin` role (see
 * README.md § Admin smoke account). Gates the admin specs so they self-skip
 * (rather than 403-fail) until that cross-repo seed is provisioned. Distinct
 * from `hasAuthCreds`: a run can be authenticated as a non-admin reader.
 */
export const SMOKE_ADMIN = /^(1|true|yes)$/i.test(process.env.STG_SMOKE_ADMIN ?? '')

/** Persisted storage-state (seeded localStorage JWT) reused across auth specs. */
export const STORAGE_STATE = join(here, '.auth', 'storage-state.json')
