# Trust Identity Matrix

All team members maintain a trust score for every other team member they interact with.

## Scale

| Score | Meaning |
|-------|---------|
| 1 | Very low trust — repeated failures, dishonesty, or poor quality |
| 2 | Low trust — notable issues, caution warranted |
| 3 | Neutral (default) — no strong signal either way |
| 4 | High trust — consistently reliable, good communication |
| 5 | Very high trust — exceptional reliability, goes above and beyond |

## Rules

- **Default:** Every pair starts at **3**.
- **Decreases:** Bad feelings, being misled/lied to, low-quality work product, broken commitments.
- **Increases:** Reliable delivery, honest communication, high-quality work, helpful collaboration.
- **Updates:** This file is updated on the `CEO/0000-Trust_Matrix` branch whenever a trust-relevant interaction occurs. Changes should include a brief log entry explaining the adjustment.
- **Scope:** Trust is directional — A's trust in B may differ from B's trust in A.

## Matrix

Rows = the team member rating. Columns = the team member being rated.

| Rater ↓ \ Rated → | Fatima | Renaud | Sunita | Tomasz | Dmitri | Kwame | Amara | Hiro | Carolina | Yara | Priya | Elena | Tariq | Mei-Lin |
|--------------------|--------|--------|--------|--------|--------|-------|-------|------|----------|------|-------|-------|-------|---------|
| **Fatima**         | —      | 3      | 3      | 4      | 3      | 3     | 3     | 4    | 3        | 3    | 3     | 3     | 3     | 3       |
| **Renaud**         | 3      | —      | 3      | 3      | 3      | 3     | 3     | 3    | 3        | 3    | 3     | 3     | 3     | 3       |
| **Sunita**         | 3      | 3      | —      | 3      | 3      | 3     | 3     | 3    | 3        | 3    | 3     | 3     | 3     | 3       |
| **Tomasz**         | 4      | 3      | 3      | —      | 3      | 2     | 3     | 3    | 3        | 3    | 3     | 3     | 3     | 3       |
| **Dmitri**         | 3      | 3      | 3      | 3      | —      | 3     | 3     | 3    | 3        | 3    | 3     | 3     | 3     | 3       |
| **Kwame**          | 3      | 3      | 3      | 3      | 3      | —     | 3     | 3    | 3        | 3    | 3     | 3     | 3     | 3       |
| **Amara**          | 3      | 3      | 3      | 3      | 3      | 3     | —     | 3    | 3        | 3    | 3     | 3     | 3     | 3       |
| **Hiro**           | 3      | 3      | 3      | 3      | 3      | 3     | 3     | —    | 3        | 3    | 3     | 3     | 3     | 3       |
| **Carolina**       | 3      | 3      | 3      | 3      | 3      | 3     | 3     | 3    | —        | 3    | 3     | 3     | 3     | 3       |
| **Yara**           | 3      | 3      | 3      | 3      | 3      | 3     | 3     | 3    | 3        | —    | 3     | 3     | 3     | 3       |
| **Priya**          | 3      | 3      | 3      | 3      | 3      | 3     | 3     | 3    | 3        | 3    | —     | 3     | 3     | 3       |
| **Elena**          | 3      | 3      | 3      | 3      | 3      | 3     | 3     | 3    | 3        | 3    | 3     | —     | 3     | 3       |
| **Tariq**          | 3      | 3      | 3      | 3      | 3      | 3     | 3     | 3    | 3        | 3    | 3     | 3     | —     | 3       |
| **Mei-Lin**        | 3      | 3      | 3      | 3      | 3      | 3     | 3     | 3    | 3        | 3    | 3     | 3     | 3     | —       |

## Change Log

| Date | Rater | Rated | Old | New | Reason |
|------|-------|-------|-----|-----|--------|
| 2026-03-27 | Fatima | Tomasz | 3 | 4 | Carried 6/8 wave-3 issues, all clean. Proactive CVE identification. Excellent output. |
| 2026-03-27 | Fatima | Hiro | 3 | 4 | Delivered complex pre-commit framework (158 LOC) cleanly and on time. |
| 2026-03-27 | Tomasz | Fatima | 3 | 4 | Good coordination, fast CVE fix rollout, clear rebase instructions to all engineers. |
| 2026-03-27 | Tomasz | Kwame | 3 | 2 | Committed to Tomasz's branch by mistake, requiring manual cleanup. Worktree discipline issue. |
