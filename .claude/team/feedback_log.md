# Team Feedback Log

Track all feedback events here. Format:

```
## [DATE] — [FROM] → [TO] — Severity: [minor/moderate/severe]
[Feedback content]
[Action taken, if any]
```

---

## 2026-03-16 — Phase 5 Retrospective (consolidated by Fatima)

### Positive
- FastAPI implementation (Kwame) was clean and well-structured; became the foundation for all subsequent API work
- React frontend (Hiro) delivered ahead of schedule with good component separation
- Carolina's test coverage work caught several edge cases before they reached production

### Areas for Improvement
- CI pipeline was fragile during Phase 5 — multiple runs needed to get green. Tomasz addressed with caching and retry improvements.
- Peer review pairing was ad-hoc; engineers self-selected reviewers, leading to uneven knowledge spread. **Action:** Added formal peer review pairing rotation to charter.

---

## 2026-03-16 — Phase 6 Retrospective (consolidated by Fatima)

### Positive
- Testcontainers approach (Kwame) gave confidence in real data flow tests — significant quality improvement over mocked tests
- Carolina's fuzz testing uncovered Arabic text edge cases that static tests missed
- Hiro's Playwright E2E tests established a reliable browser automation baseline

### Areas for Improvement
- Coverage threshold enforcement was manual — needed to be automated in CI. **Action:** Tomasz added coverage gates to GitHub Actions.
- Elena's data validation role was underutilized during this phase — most validation was done by implementers. **Action:** Clarify data team activation for future phases.

---

## 2026-03-16 — Phase 7 Retrospective (consolidated by Fatima)

### Positive
- Yara's security review was thorough and actionable — found real issues in OAuth and session handling
- Kwame's OAuth provider abstraction was well-designed, making it easy to add providers
- Amara's Fawaz Arabic data integration was smooth despite complex source format

### Areas for Improvement
- Tariq and Mei-Lin had zero contributions across all 7 phases — pure overhead. **Action:** Archived both in Phase 8 reorganization.
- Cross-team dependencies between security review and implementation caused some blocking. **Action:** Security reviews now happen in parallel with implementation where possible.
- Renaud and Dmitri had lower direct implementation involvement than expected for their seniority. Trust scores adjusted to reflect actual contribution levels.

---

## 2026-03-16 — Phase 8 Retrospective (consolidated by Fatima)

### Positive
- Wave 1 process improvements (CI hooks, commit audit, worktree cleanup) addressed long-standing tech debt
- Dmitri's tech-debt triage formalized what was previously ad-hoc tracking
- Kwame's CLI skills work improved developer ergonomics across the team
- Tomasz's hooks and scripts implementation reduced manual pre-commit checks

### Areas for Improvement
- Agent naming convention was violated multiple times before being codified. **Action:** Added explicit naming convention and mapping guide to charter.
- ADRs were missing — key architectural decisions were only in PRD or commit messages. **Action:** Created ADR log with retroactive entries for 4 key decisions.
- Feedback log was empty despite 8 phases of work. **Action:** Backfilled with retro findings from Phases 5-8.

---

## 2026-03-27 — Phase 10, Wave 3 Retrospective (consolidated by Fatima)

### Positive
- Tomasz carried 6 of 8 issues with clean, fast delivery across 4 PRs — strongest individual output this wave
- Consolidated PR approach (#355/#357/#362 in one PR) avoided merge conflicts on shared files — validated as a pattern for future waves
- Fatima's CVE catch (ecdsa 0.19.1 → 0.19.2, CVE-2026-33936) unblocked all PRs; proactive fix rolled into existing PR
- Hiro delivered the most complex feature (pre-commit framework, 158 LOC) cleanly and independently
- Bugs-before-features discipline held — all 6 bugs merged before either feature started
- Fast turnaround — all 8 issues completed in a single session

### Areas for Improvement
- **No peer reviews on any PR.** 0 of 6 PRs received peer review despite charter requirement. **Action:** Enforce peer review assignment at sprint kickoff; block merge without at least one review comment.
- **Kwame committed to wrong worktree branch.** Stray commit on Tomasz's `T.Wojcik/0355-0357-0362-docker-compose-prod-fixes` branch required manual cleanup. **Action:** Add worktree safety reminder to engineer spawn prompts; consider pre-commit hook that validates branch ownership matches committer identity.
- **Manager (Fatima) cannot spawn agents.** Spent ~5 minutes sending messages to non-existent agents before escalating. **Action:** Charter updated (§ "How to Instantiate the Team") to document that only the orchestrator can spawn agents. Feedback memory saved.
- **Lead layer (Sunita, Dmitri) was bypassed entirely.** Orchestrator spawned engineers directly for efficiency. This worked but deviates from charter's delegation model. **Action:** Accept this as pragmatic for small waves; for larger waves, spawn leads as coordination-only agents.
- **Duplicate PR created.** Both tomasz-355-357-362 (#365) and Fatima (#366) created PRs for the same consolidated fix. #365 was closed unmerged. **Action:** Clarify PR ownership — the engineer creates the PR, the manager does not duplicate it.

### Severity Assessments
- Kwame Asante — **Moderate** (wrong-branch commit). Documented, improvement expected. Trust: Tomasz→Kwame 4→3.
- Fatima Okonkwo — **Minor** (agent spawn confusion). Tooling limitation, not a judgment error. Now documented.

### No Fire/Hire Actions
No severe feedback warrants termination this wave. Kwame's error was a one-off process mistake, not a pattern.

---

## Retrospective: Phase 15 Wave 2 — 2026-04-05

### Team Performance
- **PRs merged:** 6 (#681, #682, #683, #687, #688, #689)
- **Issues closed:** 6 (#664, #668, #669, #670, #671, #678)
- **CI health:** All 6 PRs passed CI. Mateo's branches (#681, #682) each had 1 cancelled CI run (likely from force-push amends), but final runs all green.
- **Peer reviews:** 0 of 6 PRs received peer review — charter violation repeated from Wave 1/Phase 10.
- **Wave merge PR:** #690, merged to main.

### Per-Engineer Assessments

### Mateo Salazar
- PRs: #681, #682
- CI failures: 0 (2 cancelled runs from force-push amends)
- Must-fix items received: 0
- Tech-debt items created: 0
- Assessment: Delivered 2 bug fixes (login geometric bar, search results narrow column). Code quality was fine. However, initially committed PR #682 under the wrong identity (Lucas Ferreira) — required force-push amend to correct. This was partially caused by the roster.json blocker but Mateo's #681 had correct identity, suggesting inconsistency rather than purely systemic cause.
- Severity: moderate (identity discipline)

### Ingrid Lindqvist
- PRs: #687, #688
- CI failures: 0
- Must-fix items received: 0
- Tech-debt items created: 0
- Assessment: Delivered 2 PRs cleanly — one bug fix (separator graphic SVG viewBox) and one tech-debt item (extracting inline hover styles to CSS classes). Correct identity on both commits. Fast turnaround. No issues.
- Severity: none

### Jun-Seo Park
- PRs: #683
- CI failures: 0
- Must-fix items received: 0
- Tech-debt items created: 0
- Assessment: Delivered 1 tech-debt PR (deduplicating fulltext count query). Initially committed under wrong identity (Aino Virtanen) due to roster.json blocker — this was a systemic issue affecting multiple engineers, not a personal discipline failure. Corrected after fix.
- Severity: none (mitigating circumstance)

### Linh Pham
- PRs: #689
- CI failures: 0
- Must-fix items received: 0
- Tech-debt items created: 0
- Assessment: Delivered ops PR (VPS bootstrap runbook and enhanced pipeline script) cleanly with correct identity. CI green. Solid first wave contribution.
- Severity: none

### Top 3 Going Well
1. **All CI green** — every PR passed CI on final run. No broken builds merged.
2. **All 6 issues completed in one session** — fast turnaround, no stragglers or late delivery.
3. **Clean code quality** — no must-fix items, no tech-debt items generated by reviews (because there were no reviews, but also no post-merge issues found).

### Top 3 Pain Points
1. **Roster.json blocker** — org-level roster.json did not include repo-specific team members. This blocked all commits at wave start and caused 3 engineers (Mateo, Jun-Seo, and a design-system engineer Beren) to commit under wrong identities. Required force-push amends to fix.
2. **Zero peer reviews (again)** — 0 of 6 PRs received peer review. This is a repeat of the Phase 10 Wave 3 finding. Manager merged directly without requesting reviews. Charter requires at least one peer review per PR.
3. **CI not verified before presenting wave merge PR** — manager presented wave merge PR #690 to user without first checking CI status. User had to ask for CI verification. This should be a standard pre-merge checklist item.

### Proposed Process Changes
1. **Pre-merge CI verification checklist** — Manager must verify CI is green on the wave merge PR before presenting it to the user for approval. Rationale: user had to ask for CI status, which should be proactively reported.
2. **Roster.json sync on team creation** — When new repo-specific personas are created, their identities must be added to roster.json before any work begins. Add a pre-wave checklist item: "verify all assigned engineers exist in roster.json". Rationale: the roster blocker caused 3 wrong-identity commits.
3. **Enforce peer review or document exemption** — Either enforce the charter's peer review requirement (block merge without at least 1 review) or formally amend the charter to allow manager-only review for small waves. The current state — charter requires it but it never happens — is worse than either option. Rationale: 0/6 PRs reviewed, repeating Phase 10 Wave 3 finding.
