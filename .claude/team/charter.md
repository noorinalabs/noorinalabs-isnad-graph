# Repo Charter — isnad-graph

This charter supplements the org-level charter at `noorinalabs_main/.claude/team/charter.md`. All org charter rules apply. This file contains isnad-graph-specific configuration only.

## team_name

All agents working in this repo use `team_name: "isnad-graph"`.

## PRD & Scope

- **Project:** Computational hadith analysis platform (FastAPI backend, React frontend, Neo4j graph database)
- **PRD location:** `docs/hadith-analysis-platform-prd.md`
- **Phase documentation:** `docs/phase{N}-claude-code-instructions.md`

## Phase System

isnad-graph uses a phased development model. Each phase has detailed specs in `docs/`.

| Phase | Focus |
|-------|-------|
| 0 | Scaffold — models, config, utilities |
| 1 | Data acquisition & parsing |
| 2 | Entity resolution (NER, disambiguation, dedup) |
| 3 | Neo4j graph loading |
| 4 | Enrichment (metrics, topics, historical overlay) |
| 5 | FastAPI layer |
| 6 | Frontend foundation (React, routing, design system) |
| 7 | Graph explorer & visualization |
| 8 | Search & detail pages |
| 9 | Admin panel |
| 10 | Observability & production hardening |
| 11 | Authentication & authorization (OAuth, JWT, 2FA) |
| 12+ | Ongoing features, optimizations, and maintenance |

## Deployments Branching

- **Pattern:** `deployments/phase{N}/wave-{M}`
- Feature branches created from the current deployments branch
- At phase end, PR deployments branch into `main` — user merges before next phase

## Release Process

- **Tag format:** `phaseN-waveM` (e.g., `phase12-wave3`)
- **Title:** Same as the deployments branch PR title
- **Body:** Same as the PR body

## Deployment & Verification

- **Production URL:** `https://isnad-graph.noorinalabs.com`
- **Deploy workflow:** Handled by `noorinalabs-deploy` repo (see deploy repo charter)
- **Post-wave verification:** DevOps Engineer (Tomasz) verifies deployment after each wave
- **Verification steps:**
  1. Verify Deploy workflow ran: `gh run list --workflow=deploy-isnad-graph.yml -R noorinalabs/noorinalabs-deploy --limit 1`
  2. Spot-check live site: `https://isnad-graph.noorinalabs.com`
  3. Report failures to Manager immediately

## Repo-Specific Labels

- `found-in-phase{N}-wave{M}` — where a bug was discovered
- `fixed-in-phase{N}-wave{M}` — where a bug was fixed
- `p{N}-wave-{M}` — wave assignment labels
- Phase labels: `phase-0` through `phase-12`

## GitHub Repo

- **Slug:** `noorinalabs/isnad-graph`
- **Branch protection:** Ruleset ID 14482071 on `deployments/**` branches (requires 1 approving review, dismisses stale reviews)

## Build & Test Commands

See `CLAUDE.md` in the repo root for the full list. Key commands:
- `make check` — run all CI checks (lint + typecheck + test)
- `make test` — run pytest suite
- `npm run build` (from `frontend/`) — TypeScript check + Vite build
