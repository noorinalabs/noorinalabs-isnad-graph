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
| `env.ts` | Resolves target URLs + creds from env vars; exposes `hasAuthCreds`, `REQUIRE_AUTH`, `SMOKE_ADMIN`. |
| `preflight.ts` | Pure, node-free auth pre-flight (`evaluateAuthPreflight`) — decides login/skip or **throws** (loud-fail, ig#1146). Unit-tested in `src/__tests__/stgSmokePreflight.test.ts`. |
| `auth.setup.ts` | Setup project: programmatic `POST /auth/login/email` → persisted storage-state (JWT seeded into `localStorage.access_token`). Soft-skip locally when creds absent; **fails RED** when `STG_REQUIRE_AUTH=1` and creds are missing. |
| `helpers.ts` | `requireAuth()` / `requireAdmin()` skip-guards, `looksLikeHtml`, page-error collector. |
| `login.public.spec.ts` | Unauthenticated invariants — login surface + `/runtime-config.js`. Needs no creds. |
| `smoke.auth.spec.ts` | Authenticated invariants — home/narrators/hadiths/graph-explorer render + `/api/v1/search` status. Self-skips without creds. |
| `admin.auth.spec.ts` | Admin invariant — `/admin/audit` renders through the user-service `audit_log` chain (#1140 regression guard). Self-skips unless `STG_SMOKE_ADMIN=1`. |
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
| `STG_TEST_EMAIL` / `STG_TEST_PASSWORD` | _(unset)_ | Test-user creds. **Secrets only — never commit.** Absent ⇒ authenticated leg skips (locally) or **fails RED** (when `STG_REQUIRE_AUTH=1`). |
| `STG_REQUIRE_AUTH` | _(unset)_ | `1`/`true` ⇒ missing creds/URL is a **hard error** (the `e2e-stg-smoke` workflow sets it). Unset ⇒ public-only self-skip (local dev + the soft sweep). |
| `STG_SMOKE_ADMIN` | _(unset)_ | `1`/`true` ⇒ the smoke account is admin-capable, activating `admin.auth.spec.ts` + the admin sweep leg. Unset ⇒ admin specs self-skip. |

## CI

`.github/workflows/e2e-stg-smoke.yml` runs the **smoke** suite on **manual
dispatch** (with a `target_env` input) and a **daily schedule** — never on
`pull_request`, so a PR without deploy secrets is never broken by it. The
workflow publishes the HTML report always and traces/screenshots on failure.

`.github/workflows/e2e-stg-sweep.yml` runs the **exploratory sweep** on manual
dispatch + a **weekly schedule**, uploads the `sweep-results/` catalog (json +
markdown + screenshots) and the HTML report, and writes `SWEEP-CATALOG.md` into
the run summary. Unlike the smoke gate the sweep is **soft** — it does NOT set
`STG_REQUIRE_AUTH`, so a credential-less run still catalogs the public surface.

### Loud-fail vs silent-skip (ig#1146)

The smoke workflow sets **`STG_REQUIRE_AUTH=1`**, so if the authenticated leg is
not wired (missing `STG_TEST_EMAIL` / `STG_TEST_PASSWORD`, or a blanked URL) the
setup **throws** and the run reads **RED** — an unwired harness can no longer
masquerade as a green no-op. Locally (flag unset) the public leg still runs and
the auth leg self-skips, so `npm run e2e:stg` stays ergonomic without secrets.
The pure decision logic lives in `preflight.ts` and is unit-tested in
`src/__tests__/stgSmokePreflight.test.ts` — so PR CI proves the loud-fail
mechanic without a live stg environment.

### Owner-provisioned config (required for a live green run)

The harness code is complete; a live green run additionally needs the owner to
provision these (they are **out of scope for the harness PR** — the runtime
gate, not the PR's acceptance):

| Kind | Name | Purpose |
|------|------|---------|
| **Secret** | `STG_TEST_EMAIL` | Smoke test-account email (stg). |
| **Secret** | `STG_TEST_PASSWORD` | Smoke test-account password (stg). |
| Var (optional) | `STG_BASE_URL` / `STG_USER_SERVICE_URL` | Override the stg vhost defaults. |
| Var (optional) | `PROD_BASE_URL` / `PROD_USER_SERVICE_URL` | Override the prod vhost defaults (`TARGET_ENV=prod`). |
| Var (optional) | `SWEEP_NARRATOR_ID` / `SWEEP_HADITH_ID` / `SWEEP_COLLECTION_ID` | Known-good detail ids for the sweep. |
| Var (for admin) | `STG_SMOKE_ADMIN` | Set to `1` once the smoke account is admin-capable (activates `admin.auth.spec.ts`). |

### Admin smoke account (activates `admin.auth.spec.ts`)

The `/admin/audit` spec and the admin sweep leg need the smoke account to hold
the **`admin`** role. That is a **cross-repo, owner-provisioned** step — the seed
scripts live in **user-service**, not here (child-repo rule) — and **no new seed
code is required**: compose the two existing idempotent scripts against the smoke
email, then flip the var:

```bash
# In user-service, against the target (stg) user-service DB:
python scripts/bootstrap_test_user.py --email "$STG_TEST_EMAIL" --password "$STG_TEST_PASSWORD" --role reader
python scripts/bootstrap_admin.py      --email "$STG_TEST_EMAIL"   # grants admin to that same account
# Then set the repo var so the admin specs activate:
gh variable set STG_SMOKE_ADMIN --body 1
```

Optionally, wiring that composition into the **deploy** repo's post-deploy hook
(so the admin smoke account is reasserted on every stg deploy, mirroring the
existing `bootstrap_admin.py` step) is a **deploy-repo** follow-up, not an
isnad-graph change.
