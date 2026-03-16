---
name: close-stale-issues
description: Audit and close issues resolved by merged PRs
---

Audit all open GitHub issues against merged PRs.

## Instructions
1. List all open issues: `gh issue list --state open --limit 200`
2. List all merged PRs: `gh pr list --state merged --limit 200`
3. For each merged PR, check body for "Closes #N" references
4. Cross-reference: if an open issue is referenced by a merged PR, close it
5. Check tech-debt tracking issues: if all sub-issues closed, close the tracker
6. Report: issues closed, issues remaining open with reason
