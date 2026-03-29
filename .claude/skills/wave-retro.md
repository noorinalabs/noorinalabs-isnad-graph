---
name: wave-retro
description: Automated wave retrospective — PR analysis, assessments, trust matrix updates, feedback log, charter change proposals
args: Phase number, Wave number
---

Run a retrospective for a completed wave of the isnad-graph project.

## Instructions

### 1. Gather merged PRs

List all PRs merged to the wave's deployments branch:

```bash
gh pr list --state merged --base "deployments/phase{N}/wave-{M}" --json number,title,author,body,mergedAt,reviews
```

### 2. Gather review comments and CI data

For each merged PR:

```bash
gh pr view {NUMBER} --json reviews,comments
gh run list --branch {PR_BRANCH} --json conclusion,name
```

Collect:
- Review comments (must-fix items, tech-debt items)
- CI pass/fail counts per PR
- Time from PR creation to merge

### 3. Per-engineer assessment

For each engineer who had PRs in this wave, assess:

- **Positive findings:** clean PRs, fast turnaround, good reviews given, helpful collaboration
- **Negative findings:** CI failures, must-fix items from reviews, late delivery, missing tests
- **Severity:** minor / moderate / severe (per charter § Feedback System)

Structure as:

```
### {Engineer Name}
- PRs: #{N1}, #{N2}
- CI failures: {count}
- Must-fix items received: {count}
- Tech-debt items created: {count}
- Assessment: {positive/negative findings}
- Severity: {minor|moderate|severe|none}
```

### 4. Update trust matrix

Use a temporary worktree to update the trust matrix (avoids conflicts with the current working tree):

```bash
git fetch origin CEO/0000-Trust_Matrix
git worktree add /tmp/trust-matrix-update CEO/0000-Trust_Matrix
```

Update `/tmp/trust-matrix-update/.claude/team/trust_matrix.md` with directional trust changes based on wave performance:
- Reliable delivery, clean reviews → increase trust (+1, max 5)
- CI failures, must-fix items, broken commitments → decrease trust (-1, min 1)
- No significant signal → no change

Add change log entries with date and reason. Commit as the Manager (see `.claude/team/roster.json` for identity), push, then clean up:

```bash
git worktree remove /tmp/trust-matrix-update
```

### 5. Append to feedback log

Append a retro entry to `.claude/team/feedback_log.md`:

```markdown
## Retrospective: Phase {N} Wave {M} — {DATE}

### Team Performance
{summary of wave metrics: PRs merged, issues closed, CI health}

### Per-Engineer Assessments
{from step 3}

### Top 3 Going Well
1. {finding}
2. {finding}
3. {finding}

### Top 3 Pain Points
1. {finding}
2. {finding}
3. {finding}

### Proposed Process Changes
1. {change} — Rationale: {why}
2. {change} — Rationale: {why}
```

### 6. Propose charter changes

Based on pain points and findings, propose specific charter amendments. Present each as:

```
**Proposed change:** {what to change in charter}
**Section:** {which charter section}
**Rationale:** {why, based on retro findings}
```

### 7. Present to user for approval

Display all proposed changes. **Do NOT apply any charter changes without explicit user approval.** The user decides which proposals to adopt, modify, or reject.

## What remains manual

- User must approve all charter changes before they are applied
- Subjective assessment calibration (severity levels) may need user override
- Trust matrix changes are proposed — user can veto specific adjustments
