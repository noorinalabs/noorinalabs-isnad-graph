# Phase 11, Wave 3 Retrospective — Security Hardening

**Author:** Fatima Okonkwo (Manager)
**Date:** 2026-03-29
**Scope:** 10 security bugs (#440–#449) from Yara Hadid's Wave 2 auth review
**Team:** Kwame Asante, Hiro Tanaka, Carolina Méndez-Ríos, Amara Diallo
**Result:** All 10 issues closed. 5 PRs merged (#450–#453, #462). 9 tech-debt issues filed (#455–#461, #463–#464).

---

## 1. Delivery Summary

| PR | Engineer | Issues | Reviewer | Status |
|----|----------|--------|----------|--------|
| #450 | Kwame | #440 (critical JWT secret), #448 (cookie_secure) | — (critical path, fast-tracked) | Merged |
| #451 | Hiro | #441 (logout revocation), #445 (token body exposure), #446 (error leak) | Kwame | Merged |
| #452 | Amara | #444 (rate limit proxy IP), #447 (revocation multi-worker) | Carolina | Merged (2 must-fix iterations) |
| #453 | Carolina | #442 (OAuth state validation, backend + frontend) | Amara | Merged |
| #462 | Kwame | #443 (LIKE injection), #449 (password_hash lifecycle) | Hiro | Merged |

All 10 security bugs resolved. No regressions. No rollbacks.

---

## 2. What Went Well

### Bug scoping was exemplary
Yara's 10 issues came with reproduction steps, severity ratings, and recommended fixes. Engineers could start implementation immediately without ambiguity. This is the gold standard for security review output.

> **Yara's perspective:** She structured each bug report as a standalone spec — severity, affected code paths, reproduction, and recommended fix. Her view: security reviews that don't provide actionable guidance create a second round of back-and-forth that doubles the timeline. This wave proved the model works.

### Review quality was genuinely high
Every reviewer found meaningful issues. No rubber stamps.

- **Kwame** reviewing Hiro's PR #451: Caught that refresh token reads from JSON body instead of cookies — a functional gap that would have undermined the cookie-based auth model.
- **Carolina** reviewing Amara's PR #452: Found 2 blockers — missing `trusted_proxies` config field and missing `cachetools` dependency. Both would have caused runtime failures.
- **Amara** reviewing Carolina's PR #453: Caught a `response_model` conflict that would have broken the API contract.

> **Hiro's perspective:** The review assignments created genuine cross-pollination. Each reviewer had enough context from their own group to evaluate adjacent work, but enough distance to catch assumptions the author internalized. He noted this is the correct review topology for small security waves.

### Dependency ordering worked
Kwame's PR #450 (critical JWT secret fix) merged first, unblocking the rest. Grouping issues by dependency rather than arbitrary assignment prevented merge conflicts and CI cascading failures.

> **Kwame's perspective:** The issue grouping and merge ordering were solid. He appreciated that the critical-path PR was isolated — no waiting on review cycles for the highest-severity fix. He would formalize this as a standing rule: critical-severity issues always get their own PR and merge first.

### No-lead optimization was correct
With 4 engineers on 10 well-scoped bugs, spawning tech leads would have added coordination overhead without value. The orchestrator handled assignment and sequencing directly.

---

## 3. What Went Wrong

### 3.1 Spawned agents cannot SendMessage to orchestrator

**What happened:** I was spawned to create the execution plan. I wrote the plan and tried to SendMessage it back. The message was never received. The orchestrator built the plan independently, duplicating the work.

**Impact:** Delayed wave start. My planning output was wasted.

**Charter fix applied:** § Communication Limitation — agents write output to files (e.g., `/tmp/wave-plan.md`); orchestrator reads after agent goes idle.

**Assessment:** The fix is mechanically correct. The deeper issue is that spawned agents have no reliable communication channel back to the orchestrator. File-based signaling is a workaround, not a solution. It works for now, but it means every spawn requires the orchestrator to know in advance what file to poll. This is fragile if the agent's output is unstructured or if multiple agents write to the same location.

### 3.2 All agents idle simultaneously — review stall

**What happened:** All 4 engineers finished implementation around the same time, sent review requests via SendMessage, and went idle. Messages landed in idle inboxes. Nobody woke up. The user had to flag the stall.

**Impact:** Review cycle blocked until user intervention.

**Charter fix applied:** § Orchestrator Review Nudge — orchestrator monitors for all-idle states and explicitly nudges each reviewer.

> **Carolina's perspective:** The idle-stall pattern broke her flow. She had finished implementation and was ready to review immediately — but the coordination mechanism didn't support that. She advocates for the orchestrator to pre-assign review pairs before implementation starts, so both parties know the handoff point.

**Assessment:** The nudge mechanism is necessary but reactive. It still requires the orchestrator to detect the idle state — and in this wave, the orchestrator didn't detect it; the user did. The fix works only if the orchestrator actively polls. See proposed change #1 below.

### 3.3 CI failures not reported to orchestrator or user

**What happened:** 5 CI runs failed (#180, #182, #186, #187, #188) with `AttributeError: 'RateLimitSettings' has no attribute 'trusted_proxies'`. This was a cross-PR dependency — Amara's PR added the field, but other branches' CI ran against the base branch without it. Engineers rebased and fixed silently.

**Impact:** User discovered failures independently. Trust in CI green status eroded.

**Charter fix applied:** § CI Enforcement updated — engineers must notify orchestrator of ALL failures. New § Cross-PR CI Failures documents the pattern and mitigation.

> **Hiro's perspective:** The CI silence was a process failure, not a technical one. The engineers knew the failures were transient (pending Amara's merge), but "transient" is a judgment call that should be communicated, not assumed. He prefers a systematic rule: any CI red triggers a mandatory one-line status message to the orchestrator, even if the engineer considers it expected.

> **Amara's perspective:** The cross-PR dependency should have been identified during planning. Her PR introduced a config field that other PRs depended on. If the orchestrator had flagged this dependency at assignment time, the merge order could have been adjusted to avoid the cascade entirely.

**Assessment:** The charter fix addresses reporting. It does not address prevention. Cross-PR dependencies in security waves are predictable — config changes, shared middleware, new dependencies. These should be identified during planning and reflected in merge ordering. See proposed change #2.

### 3.4 Tech-debt issues not filed after PR merge

**What happened:** All 4 reviews surfaced non-blocking observations (9 total across 5 PRs). None were filed as GitHub issues by the PR creators post-merge. The orchestrator manually created 7 issues for PRs #450–#453. Only Kwame filed his 2 issues for PR #462, after the charter was updated mid-wave.

**Impact:** 9 pieces of tech debt nearly lost. Would have been invisible to future planning.

**Charter fix applied:** Step 7 added to § PR Review Workflow — post-merge tech-debt filing is a hard gate. PR not "done" until issues filed. Orchestrator verifies.

> **Kwame's perspective:** He was frustrated that this had to be enforced retroactively. Filing tech-debt issues from review comments is obvious good practice. He advocates for a pre-wave checklist that explicitly lists every post-merge responsibility, so there's no ambiguity about "done."

**Assessment:** The charter fix is sufficient. The hard gate with orchestrator verification closes the loop. Kwame's compliance after the update confirms the mechanism works when expectations are explicit.

### 3.5 Agents complete work but can't signal orchestrator

**What happened:** Three times during the wave, agents finished all work and went idle. The orchestrator had no way to detect completion — the user had to say "everyone is idle" each time.

**Impact:** Repeated user intervention. Workflow blocked on human observation.

**Charter fix applied:** § Agent Completion Signaling — agents write `/tmp/agent-status-<name>.json` on completion. Orchestrator polls.

**Assessment:** This is the same class of problem as 3.1 — agents lack a reliable signaling mechanism to the orchestrator. The file-based approach works but requires active polling. Combined with the review nudge (3.2), the orchestrator now has three polling responsibilities: completion status, idle detection, and tech-debt verification. This is manageable for small waves but will not scale. See proposed change #3.

---

## 4. Metrics

| Metric | Value |
|--------|-------|
| Issues closed | 10/10 (100%) |
| PRs merged | 5 |
| Review iterations (must-fix) | 2 (both on PR #452) |
| CI failures (transient) | 5 |
| CI failures (real bugs) | 0 |
| Tech-debt issues filed | 9 |
| Charter amendments mid-wave | 5 |
| User interventions required | 3 (idle stall, CI discovery, idle stall x2) |

---

## 5. Team Performance

| Engineer | Implementation | Review Quality | Process Compliance | Notes |
|----------|---------------|----------------|-------------------|-------|
| Kwame | Strong — critical path PR merged cleanly, second PR solid | Excellent — caught functional gap in Hiro's PR | Good — filed tech-debt issues after charter update | Model for critical-path execution |
| Hiro | Strong — 3 issues in one clean PR | Thorough — no issues noted on Kwame's #462 review | Good | Quiet, consistent delivery |
| Carolina | Strong — full-stack OAuth fix (backend + frontend) | Excellent — caught 2 blockers in Amara's PR | Acceptable | Review quality was a highlight |
| Amara | Solid — most complex group, needed 2 iterations | Good — caught response_model conflict | Acceptable | Cross-PR dependency was a planning gap, not an execution one |

---

## 6. Assessment of Charter Fixes

All 5 mid-wave charter amendments addressed real problems. Summary:

| Fix | Sufficient? | Notes |
|-----|-------------|-------|
| § Communication Limitation (file-based output) | Yes, for now | Workaround, not a solution. Works for small waves. |
| § Orchestrator Review Nudge | Partially | Requires orchestrator to detect idle state — which it didn't, initially |
| § CI Enforcement (failure reporting) | Yes | Clear rule, easy to follow |
| § Cross-PR CI Failures | Yes | Documents the pattern well |
| § Agent Completion Signaling | Yes, for now | Same class as file-based output. Adds polling burden. |
| § PR Review Workflow step 7 (tech-debt gate) | Yes | Hard gate with verification closes the loop |

---

## 7. Proposed Process Changes

These are refinements beyond the 5 charter fixes already in place. Numbered for user approval.

1. **Pre-assign review pairs at planning time, not after implementation.** Currently, review assignments happen when PRs are ready. This contributed to the idle-stall problem — engineers finished at similar times and nobody was primed to review. If review pairs are assigned during planning, both parties know the handoff point. The reviewer can monitor the PR branch and start review as soon as CI passes, without waiting for a SendMessage that may land in an idle inbox.

2. **Dependency analysis as a required planning step for security waves.** Amara's PR introduced a config field that other PRs' CI depended on. This was discoverable during planning — security bugs that touch shared config, middleware, or dependencies should be flagged, and their PRs should be ordered in the merge sequence explicitly. Add a "dependency map" step to wave planning that identifies cross-PR shared state.

3. **Consolidate agent polling into a single orchestrator checklist file.** The orchestrator now polls for: agent completion status, idle detection for review nudges, and tech-debt issue verification. Instead of separate mechanisms, define a single `/tmp/wave-status.json` file that each agent appends to. Structure: `{ "agent": "kwame", "phase": "review-complete", "pr": "#462", "tech_debt_filed": true }`. The orchestrator reads one file instead of N, and the state machine is explicit.

4. **Pre-wave checklist for engineers.** Kwame's suggestion. Before implementation starts, each engineer receives a checklist of post-merge responsibilities: file tech-debt issues, notify orchestrator of CI failures, write completion status. This makes expectations explicit and reduces mid-wave charter amendments.

5. **Security review template as a standing artifact.** Yara's bug reports were exemplary — severity, reproduction, recommended fix. Formalize this as a GitHub issue template for security reviews so future reviewers (including external ones) produce the same quality output. This is not a correction — it's codifying what worked.

6. **Critical-severity issues always get a dedicated PR and merge first.** Kwame's practice on PR #450 was correct and should be a standing rule. Critical-severity fixes should never be bundled with lower-severity issues, and they should be the first PR in the merge sequence regardless of review readiness of other PRs.

---

## 8. Closing Notes

Wave 3 delivered all 10 security fixes with zero regressions. The review quality was the highest we've seen — every reviewer found real issues. The process problems were real but contained: 5 charter amendments mid-wave is a lot, but the wave was also our stress test for the spawned-agent coordination model.

The core takeaway: our technical execution is strong. Our coordination mechanisms are the bottleneck. The proposed changes above target coordination — not because the engineers need more oversight, but because the tooling doesn't yet support the async handoff patterns that distributed agents require.

I recommend adopting changes 1–6 before Wave 4.

— Fatima
