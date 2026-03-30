# Branch & Worktree Cleanup Report

**Date:** 2026-03-29
**Author:** Tomasz Wojcik

## Summary

Cleaned up stale worktrees and merged/squash-merged remote branches to reduce repository clutter.

## Worktrees Removed: 26

### Merged to main (20 worktrees)

| Worktree | Branch |
|----------|--------|
| H.Tanaka-0302-frontend-deps-and-debt | H.Tanaka/0302-frontend-deps-and-debt |
| K.Asante-0299-rate-limiting | K.Asante/0299-gh-actions-and-rate-limiting |
| T.Wojcik-0287-terraform-and-docker-prod | T.Wojcik/0351-bootstrap-and-caddy |
| carolina-deps-debt | C.Mendez-Rios/0300-deps-and-debt |
| carolina-moderation | C.Mendez-Rios/0255-moderation-reports |
| carolina-search-550 | C.Mendez-Rios/0550-search-detail-pages |
| elena-pipeline-535 | E.Petrova/0535-full-pipeline-run |
| elena-pipeline-570 | E.Petrova/0570-0574-pipeline-bugfixes |
| elena-quality-534 | E.Petrova/0534-data-quality-gates |
| hiro-359-precommit | H.Tanaka/0359-pre-commit-hooks |
| hiro-admin-frontend | H.Tanaka/0254-admin-frontend |
| hiro-claude-code-skills | H.Tanaka/0497-0498-0499-0500-claude-code-skills |
| hiro-component-543 | H.Tanaka/0543-component-library-scaffold |
| hiro-graph-549 | H.Tanaka/0549-graph-explorer |
| kwame-observability | K.Asante/0295-observability-metrics |
| mei-ieee-578 | M.Chang/0578-ieee-hadith-assessment |
| tomasz-360-domain-v2 | T.Wojcik/0360-domain-migration |
| tomasz-deploy-552 | T.Wojcik/0552-deployment-verification |
| tomasz-ghcr-532 | T.Wojcik/0532-ghcr-implementation |
| tomasz-wave4-bugs | T.Wojcik/0338-wave4-bugs-v2 |

### Squash-merged (PR merged, remote branch deleted) (6 worktrees)

| Worktree | Branch |
|----------|--------|
| carolina-admin-polish | C.Mendez-Rios/0466-0460-0461-admin-polish |
| carolina-token-refresh | C.Mendez-Rios/0431-0432-token-refresh-fixes |
| kwame-email-auth (~/.claude/worktrees/) | K.Asante/0425-email-password-registration |
| tomasz-0418-backup | T.Wojcik/0418-backup-deploy-integration |
| tomasz-backup-deploy | H.Tanaka/0410-login-page |
| tomasz-hooks-scripts | T.Wojcik/0242-hooks-scripts |

### Kept (2 worktrees)

| Worktree | Branch | Reason |
|----------|--------|--------|
| sunita-ghcr-530 | M.Chang/0579-0581-historical-enrichment | Current working worktree |
| carolina-node24-npm-audit | deployments/phase11/wave-1 | Unmerged deployment branch |

## Remote Branches Deleted: ~131

### Merged to main (directly merged): ~98

All feature branches from A.Diallo, C.Mendez-Rios, E.Petrova, F.Okonkwo, H.Tanaka, K.Asante, M.Chang, P.Nair, R.Osei-Mensah, S.Nakamura-Whitfield, S.Krishnamurthy, T.Wojcik, and Y.Hadid that were fully merged to main.

### Squash-merged (PR merged but not git-merged): ~31

Feature branches whose PRs were merged via squash-merge on GitHub but appeared as unmerged in git. Verified via `gh pr list --state all`.

### Closed without merge: 3

- P.Nair/0493-fix-test-failures
- T.Wojcik/0354-docker-buildx-bootstrap
- T.Wojcik/0355-consolidated-docker-compose-fixes

## Remaining Unmerged Feature Branches: 2

| Branch | Status | Assessment |
|--------|--------|------------|
| A.Diallo/0025-sanadset | No PR, 1 unique commit | **Keep** -- Sanadset downloader/parser work, may be needed for future data ingestion |
| H.Tanaka/0174-real-data-testing | No PR, 1 unique commit | **Keep** -- Real data flow integration tests, potentially valuable |

## Protected Branches (not touched)

- `main`
- All `deployments/*` branches (47 total across phases 0-12)
- All `CEO/*` branches (2 total)

## Final State

| Metric | Before | After |
|--------|--------|-------|
| Remote branches | ~170+ | 52 |
| Worktrees | 29 | 3 |
| Stale remote refs | ~18 | 0 |
