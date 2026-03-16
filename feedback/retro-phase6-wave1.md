# Retrospective: Phase 6 Wave 1 (Pre-Wave)
**Date:** 2026-03-15
**Covering:** Phase 5 delivery and cumulative observations across all 5 PRD phases
**Facilitator:** Fatima Okonkwo (Manager)

---

## Project Owner Acknowledgment

Before we begin: the project owner has sent their thanks to the entire team for delivering all 5 original PRD phases. This is a meaningful milestone — the platform went from an empty repo to a working computational hadith analysis system with Neo4j graph, PostgreSQL metadata, ETL pipeline, FastAPI API, and React frontend. Every person on this team contributed to that outcome. The thanks are well-earned and I want to make sure every team member hears it directly.

---

## Team Conversations

### Engineering Team (Dmitri -> Kwame, Amara, Hiro, Carolina)

**Dmitri's summary:** "Phase 5 was the most ambitious phase we've shipped. We ran React and FastAPI development in parallel across 4 waves, which was the right call — it let us deliver frontend and backend simultaneously instead of sequentially. The team executed well under those conditions. Kwame's FastAPI work was clean and followed the patterns Renaud laid out. Amara delivered the graph and search API endpoints. Hiro built the React frontend from scratch. Carolina wrote test suites that covered both API and frontend concerns.

The honest problems: TypeScript compilation could not be verified locally because Node.js was not available in the worktrees. That means Hiro's React code was merged based on CI checks alone — we couldn't catch TypeScript errors before pushing. This is a real gap. We had to trust that what Hiro wrote would compile, and when it didn't, we only found out after the PR was already up.

The bigger issue was the CI merge gap. PRs #153, #154, and #155 were merged with failing CI checks. That's a process failure, full stop. We set up CI specifically to prevent bad code from reaching main, and then we bypassed it. The root cause was urgency — we were moving fast through Wave 2 and didn't wait for checks to pass. We caught it and corrected the process, but it shouldn't have happened.

The formatting drift pattern was a recurring annoyance. When a branch was created before formatting fixes landed on main, every file touched by that branch would show formatting diffs that weren't related to the actual work. This made reviews noisier and occasionally caused merge conflicts that were purely cosmetic. We need a better strategy for keeping branches up to date with base.

On the positive side, the bug triage process we introduced worked well. When we found that issues #160 and #165 were bugs mislabeled as tech-debt, we relabeled them with `bug` and `found-in-phase5-wave2` tags. This kind of triage discipline is new for us and I want to keep it."

**What went well:**
- Parallel FastAPI + React development across 4 waves gave us full-stack delivery without sequential bottlenecks
- Bug triage process introduced mid-phase caught mislabeled issues (#160, #165) and corrected them with proper labels
- CI pipeline (set up in Wave 0) caught formatting issues immediately — the investment in process before code paid off
- 12 tech-debt issues created during Phase 5 reviews shows the team is tracking quality gaps rather than ignoring them

**What didn't go well:**
- PRs #153-155 merged with failing CI checks — a direct violation of the process we established in Wave 0. Root cause: urgency overrode discipline
- TypeScript compilation could not be verified locally due to missing Node.js in worktrees. Hiro was effectively coding blind for type errors
- Formatting drift caused noisy diffs when branches were created before formatting fixes landed on main. This wasted reviewer time and caused unnecessary merge conflicts

**What to improve:**
- Enforce branch protection rules: require CI checks to pass before merge. No exceptions. If we set up the gate, we honor the gate
- Resolve the Node.js availability issue in worktrees so TypeScript can be verified locally before pushing
- Establish a rebase-before-review convention: before requesting review, rebase the branch onto the latest main to pick up formatting fixes and reduce diff noise

### Architecture (Renaud)

**Renaud's summary:** "The API design decisions made in Phase 5 were sound. The `/api/v1/` prefix gives us versioning room. `PaginatedResponse[T]` as a generic wrapper means every list endpoint has consistent pagination behavior — page, size, total, items. The lifespan-managed Neo4j connection pool means we're not creating connections per request, which would have been a performance disaster with graph queries.

The graph visualization choice — WebGL via a React component — was the right call for rendering large isnad networks. DOM-based rendering would have choked on graphs with thousands of narrator nodes.

My reviews caught real issues. The CORS configuration was initially too permissive (allowing all origins in what could become a production deployment). The pagination implementation had an off-by-one in the SKIP calculation. And I flagged a Cypher parameter binding issue where string interpolation was used instead of parameterized queries — that's a potential injection vector.

The one structural concern I have going forward: the API layer is thin right now. It's essentially a pass-through to Neo4j queries. That's fine for Phase 5, but if Phase 6 adds any business logic (computed fields, aggregations, caching), we'll want a service layer between the routes and the database. I'd rather design that now than retrofit it."

**What went well:**
- API versioning (`/api/v1/`), generic pagination (`PaginatedResponse[T]`), and lifespan-managed Neo4j connections were all architecturally sound decisions
- WebGL-based graph visualization was the correct choice for rendering large isnad networks
- Code review caught concrete security and correctness issues: overly permissive CORS, pagination off-by-one, Cypher string interpolation instead of parameterized queries

**What didn't go well:**
- Duplicate review feedback across concurrent PRs persisted from prior phases — when multiple PRs touch overlapping concerns (e.g., API error handling patterns), Renaud still reviews them independently and sometimes leaves contradictory or redundant comments
- No formal ADR log was created despite being proposed in the Phase 5 pre-wave retro. API contract decisions (pagination format, error schema, versioning strategy) live in PR comments, not in a central document

**What to improve:**
- Actually create the ADR log this time. Phase 5 API decisions should be retroactively documented, and Phase 6 decisions should be logged as they're made
- For Phase 6, batch-review PRs within each wave before approving any — this was proposed last retro and partially adopted, but needs to become standard practice

### DevOps (Sunita -> Tomasz, Yara)

**Sunita's summary:** "The CI pipeline is working. That's the headline. We went from zero automated checks to a GitHub Actions pipeline that runs ruff, mypy, and pytest on every PR. Tomasz set that up in Wave 0 and it caught issues immediately — exactly as intended. The Docker multi-stage builds for both API and frontend are clean: small final images, no dev dependencies in production layers.

Now the problems. The CI pipeline is slow, and the main reason is torch. Every CI run downloads PyTorch and its dependencies, which adds minutes to what should be a fast feedback loop. We need to cache those dependencies or split the pipeline so that jobs that don't need torch don't wait for it.

The Node.js issue is a real blocker for frontend development. Worktrees don't have Node.js available, which means TypeScript compilation, ESLint, and npm test can't run locally. Hiro had to push code and wait for CI to tell him if it compiled. That's a terrible developer experience and it slows down iteration. We need to either add Node.js to the worktree environment or find another solution.

Yara's security reviews during Phase 5 were more hands-on than in previous phases. She flagged the CORS issue, reviewed the authentication stubs, and checked the Docker images for unnecessary privileges. But we still don't have a security-focused test suite or automated dependency scanning. That's a gap for a project that's now exposing an API."

**What went well:**
- CI pipeline operational from Wave 0 — caught formatting and type issues immediately on PRs
- Docker multi-stage builds for API (Python/FastAPI) and frontend (React/Node) produce clean, minimal production images
- Yara's security reviews were substantive in Phase 5: CORS configuration, auth stubs, Docker privilege review

**What didn't go well:**
- CI is slow due to torch dependency downloads on every run. No dependency caching configured
- Node.js not available in worktrees — TypeScript compilation, linting, and testing impossible locally for frontend development
- PRs #153-155 merged before CI checks completed, undermining the entire purpose of the pipeline

**What to improve:**
- Add dependency caching to the CI pipeline (pip cache for Python, npm cache for Node) to cut build times significantly
- Resolve Node.js in worktrees — this is the #1 developer experience issue for Phase 6 if frontend work continues
- Enable branch protection rules requiring CI status checks to pass before merge. This prevents a repeat of the #153-155 incident

### Data Team (Elena -> Tariq, Mei-Lin)

**Elena's summary:** "Phase 5 was primarily an API and frontend phase, so the data team's direct involvement was lighter than in Phases 1-4. That said, we used the time to create two important things: a data validation framework and a pipeline profiling script. The validation framework defines expected schemas, row count bounds, null rate thresholds, and referential integrity checks for every stage of the pipeline. The profiling script instruments each pipeline stage with timing and memory metrics.

The honest caveat: neither of these has been run against real data yet. The validation framework was tested with the same synthetic fixtures we've been using since Phase 1. The profiling script exists but hasn't been executed against a full pipeline run. So we have the tools, but we don't have the evidence.

The 12 tech-debt issues created during Phase 5 reviews included data-adjacent concerns — schema documentation gaps, missing type annotations on data models, and incomplete error handling in parsers. These are all tracked and prioritized.

For Phase 6, my recommendation is the same as last retro: before we build anything else on top of the pipeline, we need to validate it with real data. The longer we wait, the more we're building on assumptions."

**What went well:**
- Data validation framework created with schema checks, row count bounds, null rate thresholds, and referential integrity rules — ready to run when real data is available
- Pipeline profiling script created for timing and memory instrumentation across all pipeline stages
- Tech-debt issues from Phase 5 reviews properly tracked, including data-adjacent concerns (schema docs, type annotations, parser error handling)

**What didn't go well:**
- Neither the validation framework nor the profiling script has been tested against real data — they exist as untested tooling
- Real-data validation remains unexecuted across all 5 phases. This is the longest-running open risk on the project

**What to improve:**
- Run the full pipeline against at least one real data source before Phase 6 implementation begins. This was recommended in the Phase 5 pre-wave retro and was not completed
- Execute the profiling script against a real pipeline run to establish baseline performance metrics before any optimization work

---

## Consolidated Themes

### Top 3 Things Going Well
1. **CI pipeline is operational and catching real issues.** The investment in Wave 0 process setup before code paid off immediately. Formatting errors, type issues, and lint violations are caught on every PR. This was the #1 pain point from the Phase 5 pre-wave retro, and it's resolved.
2. **Full-stack parallel delivery works.** Running FastAPI backend and React frontend development simultaneously across 4 waves delivered a complete web application in a single phase. The team can execute full-stack work without sequential blocking.
3. **Quality discipline is improving.** Bug triage with proper labeling was introduced. 12 tech-debt issues were proactively created during reviews. Code review continues to catch real bugs (CORS, pagination, Cypher injection). The team is getting better at tracking and categorizing quality gaps.

### Top 3 Pain Points
1. **CI checks were bypassed.** PRs #153, #154, and #155 were merged with failing CI checks. This is the most serious process failure of Phase 5. We built the gate and then walked around it. If we don't enforce branch protection rules, the CI pipeline is advisory, not preventive.
2. **Node.js unavailable in worktrees.** Frontend development was hampered by the inability to compile TypeScript, run ESLint, or execute npm tests locally. Hiro had to push-and-pray, waiting for CI to surface errors that should have been caught at the editor level. This is a developer experience problem and a velocity problem.
3. **Formatting drift creates review noise.** Branches created before formatting fixes land on main carry stale formatting, producing diffs unrelated to the actual work. This wastes reviewer time, causes cosmetic merge conflicts, and makes it harder to see what actually changed. The team needs a consistent rebase-before-review practice.

### Proposed Process Changes for Phase 6
1. **Enable GitHub branch protection rules requiring CI checks to pass before merge.** This is non-negotiable. The #153-155 incident proved that voluntary compliance is not sufficient. Sunita and Tomasz own this. Target: done before any Phase 6 code is written.
2. **Resolve Node.js availability in worktrees.** If Phase 6 includes any frontend work, the team needs local TypeScript compilation and testing. Sunita to investigate options: adding Node.js to the worktree provisioning, using a shared node_modules cache, or providing a Docker-based development environment for frontend. Target: resolved in Phase 6 Wave 0.
3. **Add CI dependency caching and establish rebase-before-review convention.** Reduce CI build times by caching pip and npm dependencies (torch downloads are the main bottleneck). Require all PRs to be rebased onto latest main before requesting review, eliminating formatting drift noise. Dmitri to enforce the rebase convention with his engineering team.
4. **Run real data through the pipeline.** This is the third consecutive retro where this has been recommended. Elena and Tariq to execute `make pipeline` against a real data source and the validation framework against the output. No more deferring. Target: Phase 6 Wave 0 or Wave 1.

---

*Next retro scheduled after Phase 6 Wave 1 completes.*
