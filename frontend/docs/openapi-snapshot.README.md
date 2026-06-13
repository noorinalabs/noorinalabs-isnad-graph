# user-service OpenAPI snapshot

This directory contains a committed snapshot of the
[`noorinalabs/noorinalabs-user-service`](https://github.com/noorinalabs/noorinalabs-user-service)
OpenAPI spec, used as the input to `npm run gen:types` (see `package.json`).
The generated output lives at `src/types/user-service.d.ts` and is committed
alongside this snapshot so a CI drift gate can fail loudly if either file is
edited without regenerating the other.

## Why committed (vs. raw-fetched at build time)

The snapshot is deterministically emitted by user-service's
`scripts/generate_openapi_snapshot.py` (sorted keys, 2-space indent, trailing
newline), making it diff-stable and review-friendly. Committing it here means:

- `npm run gen:types` is air-gappable — no network call in CI
- Reviewing this PR shows the exact upstream surface we're consuming
- Type drift is detected at PR-time, not at runtime

The tradeoff is a two-place artifact (this file + the matching one on
user-service `main`). Mitigation: the **Sync provenance** block below records
which user-service commit this snapshot was generated from. A cross-repo CI
drift gate that checks this against user-service `main` HEAD is a planned
sibling follow-up (filed once user-service publishes its first stable snapshot).

## Sync provenance

| Field | Value |
|---|---|
| **Source repo** | `noorinalabs/noorinalabs-user-service` |
| **Source commit** | `97c23f6df32ff485b61ab727916650f810cd4282` |
| **Source path** | `docs/openapi-snapshot.json` |
| **Source PR** | [noorinalabs/noorinalabs-user-service#123](https://github.com/noorinalabs/noorinalabs-user-service/pull/123) |
| **Synced on** | 2026-05-17 |
| **Synced by** | Nneka Obi (#877 P3W11) |

> **Note**: when this row is updated, the snapshot file MUST be re-synced from
> that commit and `npm run gen:types` re-run in the same change. The CI drift
> gate enforces consistency between the snapshot and the generated `.d.ts`.

### Surgical additions (not from a full re-sync)

The baseline row above is the last *full* snapshot. Individual paths/schemas
that the frontend started consuming before the next full re-sync are added
surgically (only the relevant `paths` + `components/schemas` entries, modelled
to match the user-service contract), then `npm run gen:types` is re-run. They
will be subsumed by the next full re-sync.

| Added | From user-service | Issue |
|---|---|---|
| `GET /auth/providers` (`ProvidersResponse`, `AuthProviderInfo`) | [`4587935`](https://github.com/noorinalabs/noorinalabs-user-service/commit/4587935) — `feat(auth): email login/register/providers endpoints (#43)` | [isnad-graph#1010](https://github.com/noorinalabs/noorinalabs-isnad-graph/issues/1010) |

## How to re-sync

When user-service publishes a new release (or whenever the consumer side needs
a fresh surface), update both the snapshot and the generated types in one PR:

```bash
# from frontend/
USER_SERVICE_SHA=<new-commit-sha>
curl -fsSL "https://raw.githubusercontent.com/noorinalabs/noorinalabs-user-service/${USER_SERVICE_SHA}/docs/openapi-snapshot.json" \
  -o docs/openapi-snapshot.json
npm run gen:types
# update the "Source commit" + "Synced on" + "Synced by" rows in this README
git add docs/openapi-snapshot.json docs/openapi-snapshot.README.md src/types/user-service.d.ts
git commit
```

If user-service has not yet merged its snapshot to `main`, point at the PR
head commit instead (this is how the initial bootstrap was done — see the
Source PR row above).
