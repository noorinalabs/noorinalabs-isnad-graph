---
name: wave-end
description: Finalize a wave (review, merge, cleanup)
---

Finalize the current wave.

## Instructions
1. List all open PRs targeting the current deployments branch
2. For each PR:
   a. Check CI status — do NOT proceed if failing
   b. Review the diff
   c. Post review comment (charter format)
   d. Create tech-debt issues for findings (label: next phase)
   e. Merge if CI green
   f. Close referenced issues
3. Run `git worktree prune`
4. Scan docs/ and diagrams for staleness against changes
5. If this is the final wave, create PR to main
