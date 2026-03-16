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
