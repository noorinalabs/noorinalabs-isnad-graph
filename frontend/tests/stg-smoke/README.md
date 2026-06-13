# Stg-targeted browser-automation smoke harness (#968)

A Playwright suite that drives a **real deployed environment** (staging by
default, prod in read-only/smoke-only mode) and authenticates against the live
user-service. It is the foundation the exploratory-sweep epic (#969) builds on.

> This is **separate** from the mock-based suite in `tests/e2e/` (which drives a
> local `vite preview` with every API call stubbed and is wired through the
> default `playwright.config.ts`). This harness uses its own
> `playwright.stg.config.ts` and never touches the local-mock suite.

## Layout

| File | Purpose |
|------|---------|
| `env.ts` | Resolves target URLs + creds from env vars; exposes `hasAuthCreds`. |
| `auth.setup.ts` | Setup project: programmatic `POST /auth/login/email` → persisted storage-state (JWT seeded into `localStorage.access_token`). No-op when creds absent. |
| `helpers.ts` | `requireAuth()` skip-guard, `looksLikeHtml`, page-error collector. |
| `login.public.spec.ts` | Unauthenticated invariants — login surface + `/runtime-config.js`. Needs no creds. |
| `smoke.auth.spec.ts` | Authenticated invariants — home/narrators/hadiths/graph-explorer render + `/api/v1/search` status. Self-skips without creds. |

## Run it

```bash
cd frontend
npm install
npx playwright install --with-deps chromium

# Staging (public leg only, no creds):
npm run e2e:stg

# Staging with the authenticated leg:
STG_TEST_EMAIL='qa-bot@example.com' STG_TEST_PASSWORD='…' npm run e2e:stg

# Prod (read-only / smoke-only):
TARGET_ENV=prod npm run e2e:stg
```

## Environment variables

| Var | Default | Notes |
|-----|---------|-------|
| `TARGET_ENV` | `stg` | `stg` or `prod`. |
| `STG_BASE_URL` | `https://isnad.stg.noorinalabs.com` | Frontend origin under test. |
| `USER_SERVICE_URL` | `https://users.stg.noorinalabs.com` | JWT issuer. |
| `PROD_BASE_URL` / `PROD_USER_SERVICE_URL` | prod vhosts | Used when `TARGET_ENV=prod`. |
| `STG_TEST_EMAIL` / `STG_TEST_PASSWORD` | _(unset)_ | Test-user creds. **Secrets only — never commit.** Absent ⇒ authenticated leg skips. |

## CI

`.github/workflows/e2e-stg-smoke.yml` runs on **manual dispatch** (with a
`target_env` input) and a **daily schedule** — never on `pull_request`, so a PR
without deploy secrets is never broken by it. The workflow publishes the HTML
report always and traces/screenshots on failure. Wire `STG_TEST_EMAIL` /
`STG_TEST_PASSWORD` as repo secrets and (optionally) the `*_BASE_URL` /
`*_USER_SERVICE_URL` as repo vars.
