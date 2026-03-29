---
name: wave-audit
description: Audit open issues against merged PRs — find and close orphaned issues with proper comments
args: Phase number, Wave number
---

Audit open issues for a wave and close any that were resolved but not auto-closed.

## Instructions

### 1. List merged PRs for the wave

```bash
gh pr list --state merged --base "deployments/phase{N}/wave-{M}" --json number,title,body,headRefName
```

### 2. Extract issue references from PRs

For each merged PR, parse the body for:
- `Closes #N`
- `Fixes #N`
- `Resolves #N`

Build a map: `{issue_number → [PR_number, PR_title]}`.

### 3. List open issues for the wave

```bash
gh issue list --state open --label "p{N}-wave-{M}" --json number,title,labels
```

### 4. Identify orphans

An orphan is an open issue that:
- Is labeled with the wave label (`p{N}-wave-{M}`)
- Was referenced by a merged PR's `Closes`/`Fixes`/`Resolves` but was not auto-closed

Cross-reference the two lists. Also check for issues that may have been implemented but the PR forgot to include the `Closes` reference — match by branch name pattern:

```
{FirstInitial}.{LastName}/{ISSUE_NUMBER}-*
```

### 5. Report findings to user

Present a table before taking action:

```
**Wave Audit: Phase {N} Wave {M}**

| Issue | Title | Status | Implementing PR | Action |
|-------|-------|--------|-----------------|--------|
| #123  | ...   | Open   | PR #456         | Close  |
| #789  | ...   | Open   | (none found)    | Keep   |

**Orphans found:** {count}
**Issues with no implementing PR:** {count}
```

**Do NOT close any issues until the user confirms.** Present the list and wait for approval.

### 6. Close confirmed orphans

For each confirmed orphan, close with a comment:

```bash
gh issue close {NUMBER} --comment "$(cat <<'EOF'
Closed by wave audit. This issue was resolved by PR #{PR_NUMBER} ({PR_TITLE}) which merged to `deployments/phase{N}/wave-{M}`.

Added label: `fixed-in-phase{N}-wave-{M}`
EOF
)"
```

Add the `fixed-in-phase{N}-wave{M}` label:

```bash
gh issue edit {NUMBER} --add-label "fixed-in-phase{N}-wave-{M}"
```

### 7. Report summary

```
**Audit complete:**
- Issues closed: {count}
- Issues remaining open: {count} (no implementing PR found)
- Issues already closed: {count} (correctly auto-closed)
```

## What remains manual

- User must approve all closures before they execute
- Issues with no implementing PR require manual triage (defer, reassign, or close as won't-fix)
- The skill does not verify that the PR actually implemented the issue — it relies on `Closes #N` references and branch naming conventions
