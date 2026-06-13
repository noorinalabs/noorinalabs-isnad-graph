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
| `exploratory.sweep.public.ts` | **Exploratory sweep (#969)** — walks every anonymous route, catalogs load/console/network status. Soft checks. |
| `exploratory.sweep.auth.ts` | **Exploratory sweep (#969)** — walks every protected + admin route, catalogs load/console/network/empty-state status. Self-skips without creds. |
| `sweep/routes.ts` | Route inventory the sweep walks (mirrors `src/App.tsx`). |
| `sweep/catalog.ts` | `visitAndCatalog` (per-route diagnostics → record) + `softAssert`. |
| `sweep/aggregate.mjs` | Folds per-route records into `sweep-results/sweep-catalog.json` + `SWEEP-CATALOG.md`. |

## Smoke vs sweep

| | **Smoke** (`*.spec.ts`, #968) | **Sweep** (`*.sweep.*.ts`, #969) |
|---|---|---|
| Purpose | Assert a few load-bearing invariants (gate-grade) | Catalog the *whole* surface: what works vs what's missing |
| On a gap | Hard fail | Soft — records it, the walk continues |
| Output | pass/fail | `SWEEP-CATALOG.md` + per-route records + screenshots |
| Scope | login, runtime-config, home/narrators/hadiths/graph, search status | every route in `sweep/routes.ts` (anon + auth + admin) |

## Run it

```bash
cd frontend
npm install
npx playwright install --with-deps chromium

# --- Smoke (#968): a few invariants, hard-fails on regression ---
# Staging (public leg only, no creds):
npm run e2e:stg
# Staging with the authenticated leg:
STG_TEST_EMAIL='qa-bot@example.com' STG_TEST_PASSWORD='…' npm run e2e:stg
# Prod (read-only / smoke-only):
TARGET_ENV=prod npm run e2e:stg

# --- Exploratory sweep (#969): walk + catalog the whole surface ---
# (public leg always runs; auth + admin legs need creds / an admin test user)
STG_TEST_EMAIL='qa-bot@example.com' STG_TEST_PASSWORD='…' npm run e2e:sweep
npm run sweep:report   # → frontend/sweep-results/SWEEP-CATALOG.md
```

Per-route detail-ids (`/narrators/:id`, `/hadiths/:id`, `/collections/:id`)
default to fixture ids; override with a known-good id for the target env via
`SWEEP_NARRATOR_ID` / `SWEEP_HADITH_ID` / `SWEEP_COLLECTION_ID` so a wrong id
doesn't masquerade as a broken page.

## Environment variables

| Var | Default | Notes |
|-----|---------|-------|
| `TARGET_ENV` | `stg` | `stg` or `prod`. |
| `STG_BASE_URL` | `https://isnad.stg.noorinalabs.com` | Frontend origin under test. |
| `USER_SERVICE_URL` | `https://users.stg.noorinalabs.com` | JWT issuer. |
| `PROD_BASE_URL` / `PROD_USER_SERVICE_URL` | prod vhosts | Used when `TARGET_ENV=prod`. |
| `STG_TEST_EMAIL` / `STG_TEST_PASSWORD` | _(unset)_ | Test-user creds. **Secrets only — never commit.** Absent ⇒ authenticated leg skips. |

## CI

`.github/workflows/e2e-stg-smoke.yml` runs the **smoke** suite on **manual
dispatch** (with a `target_env` input) and a **daily schedule** — never on
`pull_request`, so a PR without deploy secrets is never broken by it. The
workflow publishes the HTML report always and traces/screenshots on failure.

`.github/workflows/e2e-stg-sweep.yml` runs the **exploratory sweep** on manual
dispatch + a **weekly schedule**, uploads the `sweep-results/` catalog (json +
markdown + screenshots) and the HTML report, and writes `SWEEP-CATALOG.md` into
the run summary.

Wire `STG_TEST_EMAIL` / `STG_TEST_PASSWORD` as repo secrets and (optionally) the
`*_BASE_URL` / `*_USER_SERVICE_URL` and `SWEEP_*_ID` values as repo vars.
