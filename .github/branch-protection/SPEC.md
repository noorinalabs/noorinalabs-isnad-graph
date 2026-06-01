# Branch Protection — noorinalabs-isnad-graph (P3 end-state #4, main#322)

Phase-3 end-state criterion #4 (`noorinalabs-main#322`): **CI failures block all
merges** on every repo's default branch, org-wide — enforced server-side by
GitHub, not only by the Hook 4 comment-gate. This directory carries the
canonical ruleset for this repo's `main`:

| File | Purpose |
|------|---------|
| `ruleset-main.json` | The repository ruleset payload (GitHub REST `/rulesets`). |
| `apply-ruleset.sh`  | Owner/admin-gated apply + read-back-verify. Idempotent (create-or-update). |
| `SPEC.md`           | This document — the shape and the why. |

This is isnad-graph's adoption of the parent-canonical spec
(`noorinalabs-main` charter `pull-requests.md` § *Org-Wide Branch Protection +
Admin-Merge Exceptions*), modeled on the W13 live pilot
(`noorinalabs-data-acquisition`, ruleset id `17091263`) and the W14 sibling
adoptions (`noorinalabs-user-service` #141, `noorinalabs-landing-page` #104).

## Pre-existing protection on this repo

Unlike most siblings, isnad-graph already carried partial default-branch
protection before this rollout:

- A **classic branch-protection** rule on `main` requiring the status checks
  `test`, `lint-and-typecheck`, `security-audit` (no required PR / no admin
  enforcement).
- A separate **active ruleset** *"Require review on deployments branches"*
  (id `14482071`) that targets the `deployments/**` branches — NOT `main` — and
  is out of scope here.

The ruleset in this directory is named *"Protect main — …"* (distinct from both
of the above), so applying it does **not** collide with or replace them. It is a
**superset** of the classic rule's contexts plus the PR + deletion +
non-fast-forward + admin-bypass shape. The owner may retire the now-redundant
classic rule after the ruleset is verified live; that cleanup is optional and
out of scope for this PR.

## Application status

The **spec + apply script** land in this PR (W14, `Refs noorinalabs-main#322`).
The actual **apply is owner/admin-gated** and is a **post-merge step**:

1. Creating a repository ruleset requires repo-admin permission, which the agent
   `gh` principal (`parametrization`) does not hold for this purpose.
2. Applying default-branch protection while a wave-branch PR is in flight can
   block our own merges, so the apply runs from a window with **no in-flight
   default-branch merge** — post-wave-wrapup is the safe window.

So #322 is **met for this repo only when the owner has run `apply-ruleset.sh`
and read-back-verified the ruleset on `main`.** `#322` stays OPEN as the
org-wide rollout tracker until all default branches carry the protection.

## The ruleset shape (and why)

A **repository ruleset** targeting `~DEFAULT_BRANCH`, `enforcement: active`:

- **`pull_request` with `required_approving_review_count: 0`** — the load-bearing
  decision. GitHub's "require approvals" counts **formal** GitHub PR reviews,
  which our team structurally cannot produce: the `gh` auth principal IS the PR
  author (`parametrization`), so a formal self-approval **422s**, and our review
  discipline runs on **issue-comment verdicts** validated by Hook 4
  (`validate_pr_review`), not formal reviews. A naive "require 1 approval" rule
  would **deadlock every merge**. Reviewer-count enforcement stays with Hook 4.
- **`required_status_checks` (strict)** — isnad-graph has **unconditional PR CI**
  (`ci.yml` has no `paths:` filter; it runs on every PR to `main` /
  `deployments/**`), so the ruleset hard-requires its gate **job-name** contexts:

  | Context | Source job (`ci.yml`) |
  |---------|-----------------------|
  | `lint-and-typecheck` | ruff check + ruff format --check + mypy |
  | `security-audit` | pip-audit + gitleaks |
  | `test` | pytest (`--cov-fail-under=70`) |
  | `frontend-lint-and-test` | eslint + type-drift + tsc + vitest |
  | `hooks-lint` | ruff over `.claude/hooks/` (no-ops cleanly when empty) |
  | `scripts-lint` | ruff over `scripts/` |
  | `lockfile-validation` | reject local `file://` paths in package-lock.json |

  **Excluded on purpose:**
  - `e2e` — currently `if: false` (disabled pending the mock-auth-refresh,
    isnad-graph#812). A required context that never reports would **deadlock**
    every merge; re-add `{ "context": "e2e" }` only when #812 re-enables the job.
  - `precommit-ci-sync` (and the other `docs.yml` jobs) — `docs.yml` is
    **`paths:`-filtered**, so on a PR that touches no docs/config path the job
    does not run and would not report. A `paths`-filtered job must **not** be a
    hard-required status check (it would block code-only PRs). If `docs.yml` is
    later made unconditional, add `{ "context": "precommit-ci-sync" }` here.

  **Re-confirm all contexts at apply time** against live check-runs — job names
  can change:
  `gh api repos/noorinalabs/noorinalabs-isnad-graph/commits/<default-sha>/check-runs --jq '.check_runs[].name'`.
- **`deletion` + `non_fast_forward`** — no force-push / branch-delete on `main`.
- **`bypass_actors`: Repository-admin (`actor_id: 5`, `bypass_mode: always`)** —
  keeps the orchestrator's `--admin` wave→main wrapup merges and the charter
  single-reviewer / doc-sweep / emergency exceptions working. The GitHub-side
  bypass is mirrored on the operator side by the hook-validated
  `ADMIN_MERGE_EXCEPTION` gate (`validate_pr_ci_status`), which **audits** every
  `--admin` merge to the Annunaki trail — defense in depth: the ruleset covers
  UI/external/batch-loop merges, the hook covers `gh pr merge` and names the
  exceptions.

## How to apply (owner)

```bash
# From a window with NO in-flight default-branch merge (post-wave-wrapup):
.github/branch-protection/apply-ruleset.sh            # create or update
DRY_RUN=1 .github/branch-protection/apply-ruleset.sh  # preview only

# Then read-back-verify the detail (contexts + bypass actor):
gh api repos/noorinalabs/noorinalabs-isnad-graph/rulesets \
  --jq '.[] | select(.name|startswith("Protect main")) | .id'
gh api repos/noorinalabs/noorinalabs-isnad-graph/rulesets/<id>
```
