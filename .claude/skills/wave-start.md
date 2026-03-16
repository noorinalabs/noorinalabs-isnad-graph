---
name: wave-start
description: Initialize a new wave
---

Initialize a new wave for the isnad-graph project.

## Instructions
1. Run `git worktree prune` to clean stale worktrees
2. Determine base branch (previous wave's deployments branch, or main for wave-1)
3. Create `deployments/phase{N}/wave{M}` from the base
4. Push to origin
5. Run the `/retro` skill if this is not wave-0
6. Report the branch URL
