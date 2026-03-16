---
name: review-pr
description: Review a PR using charter format
args: PR number
---

Review a pull request following the team charter.

## Instructions
1. Fetch PR diff: `gh pr diff {number}`
2. Check CI status: `gh pr checks {number}` — report if failing
3. Review for: correctness, error handling, test coverage, ruff/mypy compliance
4. Post review comment using charter format:
   ```
   Requestor: Dmitri.Volkov
   Requestee: {PR author from charter}
   RequestOrReplied: Request

   **Review: {LGTM or issues}**
   Must-fix: {list or "None"}
   Tech-debt: {list or "None"}
   ```
5. For each tech-debt item, create GitHub Issue (label: tech-debt + next phase + author)
6. Report: findings, CI status, merge readiness
