---
name: retro
description: Run a wave retrospective
---

Run a wave retrospective for the isnad-graph project.

## Instructions
1. Collect all PRs merged into the current wave's deployments branch: `gh pr list --state merged --base deployments/phase{N}/wave{M}`
2. Collect all issues closed during this wave
3. Collect all tech-debt issues created during this wave
4. Count CI failures per PR via `gh run list`
5. Write retrospective to `feedback/retro-phase{N}-wave{M}.md` with sections:
   - Team Conversations (each lead)
   - Top 3 Going Well
   - Top 3 Pain Points
   - Proposed Process Changes
6. Commit as the Manager (see `.claude/team/roster.json` for identity)
