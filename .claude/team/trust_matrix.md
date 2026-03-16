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

*Note: Tariq and Mei-Lin archived after Phase 8 reorganization — removed from active matrix.*

| Rater ↓ \ Rated → | Fatima | Renaud | Sunita | Tomasz | Dmitri | Kwame | Amara | Hiro | Carolina | Yara | Priya | Elena |
|--------------------|--------|--------|--------|--------|--------|-------|-------|------|----------|------|-------|-------|
| **Fatima**         | —      | 3      | 3      | 4      | 3      | 5     | 4     | 4    | 4        | 4    | 3     | 3     |
| **Renaud**         | 3      | —      | 3      | 3      | 3      | 4     | 4     | 4    | 4        | 3    | 3     | 3     |
| **Sunita**         | 3      | 3      | —      | 4      | 3      | 4     | 3     | 3    | 3        | 4    | 3     | 3     |
| **Tomasz**         | 3      | 3      | 4      | —      | 3      | 4     | 3     | 3    | 3        | 4    | 3     | 3     |
| **Dmitri**         | 3      | 3      | 3      | 3      | —      | 5     | 4     | 4    | 4        | 3    | 3     | 3     |
| **Kwame**          | 4      | 3      | 3      | 4      | 4      | —     | 4     | 4    | 4        | 3    | 3     | 3     |
| **Amara**          | 4      | 3      | 3      | 3      | 4      | 4     | —     | 4    | 4        | 3    | 3     | 3     |
| **Hiro**           | 4      | 3      | 3      | 3      | 4      | 4     | 4     | —    | 4        | 3    | 3     | 3     |
| **Carolina**       | 4      | 3      | 3      | 3      | 4      | 4     | 4     | 4    | —        | 3    | 3     | 3     |
| **Yara**           | 3      | 3      | 4      | 4      | 3      | 3     | 3     | 3    | 3        | —    | 3     | 3     |
| **Priya**          | 3      | 3      | 3      | 3      | 3      | 3     | 3     | 3    | 3        | 3    | —     | 3     |
| **Elena**          | 3      | 3      | 3      | 3      | 3      | 3     | 3     | 3    | 3        | 3    | 3     | —     |

## Change Log

| Date | Rater | Rated | Old | New | Reason |
|------|-------|-------|-----|-----|--------|
| 2026-03-16 | Fatima | Kwame | 3 | 5 | Consistent high-quality delivery across all 8 phases — core implementer for acquire, parse, resolve, enrich, API, testcontainers, OAuth, and CLI skills |
| 2026-03-16 | Fatima | Amara | 3 | 4 | Reliable delivery on NER, disambiguation, edges, graph API, historical overlay, and Fawaz Arabic work |
| 2026-03-16 | Fatima | Hiro | 3 | 4 | Solid contributions to validation, dedup, topics, React frontend, real data tests, Playwright, and sunnah scraper |
| 2026-03-16 | Fatima | Carolina | 3 | 4 | Strong test coverage work, OpenHadith/Sunnah parsing, fuzz testing, metadata, and GitHub Pages |
| 2026-03-16 | Fatima | Tomasz | 3 | 4 | Reliable CI/CD, Docker fixes, coverage/license tooling, hooks/scripts, and worktree cleanup throughout |
| 2026-03-16 | Fatima | Yara | 3 | 4 | Strong security review contributions in Phase 7 |
| 2026-03-16 | Dmitri | Kwame | 3 | 5 | Most prolific and reliable engineer on the team across all phases |
| 2026-03-16 | Dmitri | Amara | 3 | 4 | Consistently reliable on data-heavy implementation work |
| 2026-03-16 | Dmitri | Hiro | 3 | 4 | Versatile — handled backend validation, frontend React, E2E testing |
| 2026-03-16 | Dmitri | Carolina | 3 | 4 | Strong on testing and parsing, dependable delivery |
| 2026-03-16 | Kwame | Fatima | 3 | 4 | Good project management, clear task delegation |
| 2026-03-16 | Kwame | Dmitri | 3 | 4 | Fair tech lead, good code review feedback |
| 2026-03-16 | Kwame | Tomasz | 3 | 4 | CI always works, responsive to infrastructure needs |
| 2026-03-16 | Kwame | Amara | 3 | 4 | Great collaborator on shared modules |
| 2026-03-16 | Kwame | Hiro | 3 | 4 | Reliable peer, good cross-domain skills |
| 2026-03-16 | Kwame | Carolina | 3 | 4 | Thorough testing, catches edge cases |
| 2026-03-16 | Amara | Kwame | 3 | 4 | Strong technical partner |
| 2026-03-16 | Amara | Dmitri | 3 | 4 | Constructive code reviews |
| 2026-03-16 | Amara | Fatima | 3 | 4 | Clear expectations, good communication |
| 2026-03-16 | Hiro | Kwame | 3 | 4 | Reliable and knowledgeable |
| 2026-03-16 | Hiro | Dmitri | 3 | 4 | Helpful tech lead guidance |
| 2026-03-16 | Hiro | Fatima | 3 | 4 | Good project coordination |
| 2026-03-16 | Carolina | Kwame | 3 | 4 | Strong code quality |
| 2026-03-16 | Carolina | Dmitri | 3 | 4 | Fair reviewer |
| 2026-03-16 | Carolina | Fatima | 3 | 4 | Clear direction |
| 2026-03-16 | Sunita | Tomasz | 3 | 4 | Implements infrastructure designs faithfully |
| 2026-03-16 | Sunita | Yara | 3 | 4 | Good security collaboration |
| 2026-03-16 | Tomasz | Sunita | 3 | 4 | Clear architectural guidance |
| 2026-03-16 | Tomasz | Yara | 3 | 4 | Security reviews are actionable |
| 2026-03-16 | Yara | Sunita | 3 | 4 | Infrastructure design is security-conscious |
| 2026-03-16 | Yara | Tomasz | 3 | 4 | Responsive to security fix requests |
| 2026-03-16 | Renaud | Kwame | 3 | 4 | Architecturally sound implementations |
