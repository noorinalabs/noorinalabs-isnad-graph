# Retrospective: Phase 8 Wave 1 (Pre-Wave)
**Date:** 2026-03-16
**Covering:** Phase 7 delivery (Security, Ops, Deployment, Platform)
**Facilitator:** Fatima Okonkwo (Manager)

---

## Context

Phase 7 was the security and operations phase, delivered in 3 waves. Wave 1 retooled the data layer — Fawaz Arabic editions, a sunnah.com scraper, and metadata enrichment — plus resolved 9 tech debt items. Wave 2 implemented the OAuth authentication shim (4 providers with PKCE) and produced the 2FA design doc, alongside OWASP hardening. Wave 3 delivered Swagger API documentation, CI optimization (combined jobs and caching), diagram updates, an agent teams improvements doc, and a team interaction audit. This was the first phase where Yara (Security Engineer) did primary implementation work rather than review-only.

---

## Top 3 Things Going Well

1. **Yara delivered as implementer, not just reviewer.** The Phase 6 retro called for Yara to be embedded from Wave 0 as a primary implementer. She co-owned the OAuth auth shim and OWASP hardening in Wave 2. This was the first time a security engineer shipped feature code on this project, and the auth implementation is stronger for it. The model of embedding specialists as implementers works.

2. **CI optimization paid off.** Wave 3 combined CI jobs, added uv caching, and introduced concurrency controls. Build times dropped and the pipeline is cleaner. Tomasz caught the branch protection mismatch (old job names vs new combined job names) before it caused a merge incident — a near-miss that validates the practice of auditing CI configuration after structural changes.

3. **Tech debt was systematically addressed.** Wave 1 closed 9 tech debt items alongside feature work. This is the first time tech debt was treated as a first-class deliverable within a wave rather than deferred to "later." The debt backlog is shrinking instead of growing.

---

## Top 3 Pain Points

1. **Wave 2 CI failures on both PRs.** The OAuth PR (security.py Unicode crash, pip-audit failing on local packages, mypy no-any-return errors) and the OWASP PR (cross-PR dependency on a twofa module that hadn't merged yet) both failed CI on initial submission. These were not obscure edge cases — they were dependency ordering, tool configuration, and type-checking issues that should have been caught before PR creation. Local validation before pushing remains inconsistent.

2. **Branch protection mismatch was a process gap.** When CI jobs were renamed/combined in Wave 3, the branch protection rules still referenced the old job names. This would have silently allowed PRs to merge without checks. It was caught manually, but we had no automated validation that branch protection rules match actual CI job names. This is a fragile link in the safety chain.

3. **Agent naming convention violations.** The team interaction audit in Wave 3 identified that many functional agents were spawned without proper persona mapping from the roster. This erodes the team simulation model — if agents aren't operating under their assigned identities, commit attribution, feedback tracking, and accountability all degrade. The charter rules exist but enforcement was lax.

---

## Proposed Process Changes for Phase 8

1. **Local CI pre-check before PR creation.** Every code-writing agent must run `make lint`, `make typecheck`, and relevant tests locally before pushing a PR. The Wave 2 failures (Unicode crash, mypy errors, missing module dependency) were all locally reproducible. Add this as an explicit step in the team charter.

2. **CI job name audit after pipeline changes.** Any PR that modifies CI workflow files must include verification that branch protection rules still reference valid job names. Tomasz to own this check — it can be a manual step for now, automated later.

3. **Enforce agent persona mapping.** All spawned agents must map to a roster member. The manager (me) will verify persona assignment at task creation time. Agents operating outside the roster will be flagged in wave retros.

4. **Cross-PR dependency sequencing.** When work spans multiple PRs with dependencies, the manager must define and communicate merge order before implementation begins. The Wave 2 twofa module incident happened because two PRs were developed in parallel with an undeclared dependency. Declare dependencies upfront, merge in order.

---

*Next retro scheduled after Phase 8 Wave 1 completes.*
