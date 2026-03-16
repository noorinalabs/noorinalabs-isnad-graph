# Retrospective: Phase 5 Wave 1 (Pre-Wave)
**Date:** 2026-03-15
**Covering:** Phases 0-4 learnings before Phase 5 begins
**Facilitator:** Fatima Okonkwo (Manager)

---

## Team Conversations

### Engineering Team (Dmitri -> Kwame, Amara, Hiro, Carolina)

**Dmitri's summary:** "The team shipped consistently across all four phases. We ran parallel worktrees for each engineer per wave, which gave us real velocity — four engineers could work on independent issues simultaneously without stepping on each other. The main friction was worktree branch confusion: on at least three occasions, commits landed on the wrong branch because an engineer's worktree HEAD drifted or they forgot which worktree they were in. Kwame's orchestrator work on Phase 1 (#49) and Phase 4 (#131) was clean every time. Amara's edge loading (#101) and disambiguation (#73) were solid implementations. Hiro caught real tech debt issues consistently. Carolina's test suites (#50, #132) gave us confidence in each phase before merging. Priya hasn't had formal QA cycles yet — all testing has been unit/integration tests written by the engineers themselves."

**What went well:**
- Parallel worktree execution gave the team 3-4x throughput per wave — four engineers shipping simultaneously with minimal merge conflicts
- Tech debt was tracked as explicit issues and addressed in dedicated waves (e.g., Phase 3 tech debt batch: #95-#99, Phase 4: #116-#119), preventing accumulation
- Code quality stayed high across 134 commits — ruff and mypy strict mode caught issues early, no regressions slipped through
- Each phase followed a consistent pattern: module setup -> implementation -> tech debt -> tests -> orchestrator -> merge, which reduced coordination overhead

**What didn't go well:**
- Worktree branch confusion caused commits to land on wrong branches at least 3 times — this required manual cherry-picks and force operations to fix. Root cause: engineers didn't verify their worktree HEAD before committing
- Issue closure lagged behind PR merges in early phases. Issues were left open even after the corresponding branch was merged to main. This was caught and corrected by Phase 3, but it created a misleading project board for Phases 1-2
- Priya (QA) has been underutilized — no dedicated QA passes or test plans beyond what engineers wrote themselves. For Phase 5 (API + frontend), this gap will hurt

**What to improve:**
- Add a pre-commit check or checklist step: verify branch name matches issue number before pushing. Consider a git hook that validates branch naming convention
- Assign Priya real QA ownership for Phase 5 — she should write test plans for API endpoints and review test coverage, not just rubber-stamp engineer-written tests
- Close issues immediately when PRs merge. Use GitHub's "Closes #N" syntax in PR descriptions to automate this

### Architecture (Renaud)

**Renaud's summary:** "The architecture held up well. The monorepo layout under src/ with clean module boundaries (acquire, parse, resolve, graph, enrich) meant each phase could be built independently. My review comments caught real bugs — the MATCH vs MERGE issue in edge loaders (#101) could have caused duplicate relationships in production, and the enum serialization pattern I flagged early in Phase 0 prevented downstream Parquet schema mismatches. The one thing I'd change: when multiple agents touched overlapping files in the same wave, I ended up leaving similar review comments on different PRs because I couldn't see the other reviews in flight."

**What went well:**
- Schema-first design paid off — Pydantic models (frozen, strict) caught data issues at parse time rather than at graph load time
- The MATCH vs MERGE catch on edge loaders (commit ccb969b) prevented what would have been a serious data integrity bug in Neo4j
- Module boundaries were clean enough that four engineers could work in parallel without import conflicts or circular dependencies
- Review comments were substantive: no rubber stamps, every comment referenced a concrete risk or improvement

**What didn't go well:**
- Duplicate review comments across concurrent PRs in the same wave. When Amara and Kwame both touched graph module files in Phase 3, Renaud left overlapping feedback on both PRs because he reviewed them independently
- No formal architecture decision records (ADRs) — decisions like "PyArrow as intermediate format" and "MERGE for idempotency" were made in PR comments and commit messages, not documented centrally

**What to improve:**
- For Phase 5, batch-review PRs within each wave before approving any. This prevents duplicate/contradictory feedback and gives a holistic view
- Start a lightweight ADR log in docs/ — even a single file with one-line decisions and the PR number where each was made. This becomes critical in Phase 5 where API contract decisions will compound

### DevOps (Sunita -> Tomasz, Yara)

**Sunita's summary:** "Docker Compose setup was quick and clean — Neo4j, PostgreSQL with pgvector, and Redis all running locally with health checks. Tomasz handled the infrastructure files well. Yara's security reviews caught subprocess timeout issues and credential handling gaps early. The elephant in the room: we have no CI/CD pipeline. All 134 commits were tested locally by individual engineers. We've been relying on discipline rather than automation, and that's a risk that grows with Phase 5."

**What went well:**
- Docker Compose infrastructure was production-ready from Phase 0 — health checks, named volumes, proper networking
- Subprocess timeout enforcement and credential handling (SUNNAH_API_KEY, KAGGLE_KEY) were caught and fixed in review before they became security issues
- Makefile targets provided consistent developer experience across all phases (make test, make lint, make pipeline)

**What didn't go well:**
- No CI/CD pipeline exists. Zero automated checks on PRs — no lint gate, no test gate, no type-check gate. Every PR was manually verified by the engineer before merge. This is the single biggest process gap heading into Phase 5
- No integration testing against real infrastructure — all tests mock Neo4j and PostgreSQL. We don't know if the pipeline actually works end-to-end against real databases
- Yara has been reviewing in an advisory capacity only. No security-focused test suite, no dependency scanning, no secret detection in commits

**What to improve:**
- GitHub Actions CI pipeline is the #1 priority before Phase 5 implementation begins. Minimum: ruff + mypy + pytest on every PR. This is non-negotiable
- Add a docker-compose.test.yml for integration tests that spin up real Neo4j and PostgreSQL, run the pipeline with sample data, and validate graph state
- Yara should own a security checklist for the API layer in Phase 5 — input validation, auth, rate limiting, CORS

### Data Team (Elena -> Tariq, Mei-Lin)

**Elena's summary:** "The data pipeline design is solid on paper. Every parser emits validated Parquet with PyArrow schemas, data quality metrics are logged at each stage, and the staging format is clean enough for downstream consumers. Tariq's schema work and Mei-Lin's entity resolution approach were both well-thought-out. But here's the honest truth: we've never run the full pipeline with real data. All parser tests use synthetic fixtures. We don't know what the real Sunnah.com API response looks like at scale, we don't know how the LK corpus parser handles the full 60,000+ hadith corpus, and we don't know if entity resolution actually works on real Arabic names with real diacritics variation."

**What went well:**
- Data quality metrics embedded in every parser (row counts, null rates, schema validation) — this will make debugging real data issues much faster
- PyArrow staging schema as intermediate format was a good architectural call — it decouples raw format quirks from graph loading logic
- Entity resolution pipeline (NER -> disambiguation -> dedup) has clean stage boundaries, making it testable in isolation

**What didn't go well:**
- Zero real-data validation. All 7 parsers have been tested with hand-crafted fixtures only. We don't know failure modes for real API responses, malformed CSV rows, or Arabic text edge cases at scale
- No data profiling or exploratory analysis on actual source data. We designed schemas based on API documentation and sample files, not empirical observation
- Mei-Lin's CAMeLBERT and FAISS integration for entity resolution is specced but the actual model behavior on hadith narrator names is untested

**What to improve:**
- Before Phase 5 API work begins, run the full pipeline (make pipeline) against at least one real data source end-to-end. Even a subset of Sunnah.com would surface real issues
- Create a data profiling notebook that downloads sample data from each source and validates our schema assumptions
- Document known data quality risks: encoding issues, missing fields, API rate limits, corpus size estimates

---

## Consolidated Themes

### Top 3 Things Going Well
1. **Parallel execution model works.** Worktrees + dedicated issues + wave-based batching gave us consistent 3-4x throughput. 134 commits across 4 phases with minimal merge conflicts proves the model scales.
2. **Code quality discipline is strong.** Ruff + mypy strict mode + substantive code reviews caught real bugs (MATCH vs MERGE, enum serialization, subprocess timeouts). No known regressions in main.
3. **Architecture held up.** The monorepo module structure, Pydantic-first schema design, and PyArrow staging format all proved to be good early decisions. No major refactors were needed across phases.

### Top 3 Pain Points
1. **No CI/CD pipeline.** 134 commits, zero automated gates. We've been lucky — discipline held — but Phase 5 (API + frontend) introduces attack surface that can't be covered by "trust the engineer ran make test."
2. **No real-data validation.** The entire pipeline has been tested with synthetic fixtures. We don't actually know if it works. This is a time bomb if Phase 5 builds an API on top of data that was never loaded.
3. **Worktree branch confusion.** Commits landing on wrong branches happened multiple times. Each incident cost 30-60 minutes of git surgery. With Phase 5's increased concurrency (API + frontend + data), this will get worse.

### Proposed Process Changes for Phase 5
1. **Stand up GitHub Actions CI before any Phase 5 code.** Minimum pipeline: ruff lint, mypy typecheck, pytest with coverage gate. Every PR must pass before merge. Tomasz and Sunita own this. Target: done before Wave 1 implementation starts.
2. **Run real data through the pipeline.** Before building an API on top of the graph, validate that the graph contains real data. Elena and Tariq run `make pipeline` against Sunnah.com (subset) and at least one Shia source (Thaqalayn). Document what breaks.
3. **Enforce branch verification.** Add a pre-push git hook that validates the branch name matches the `{F.LastName}/{NNNN}-{description}` pattern and that the issue number exists. This eliminates the worktree branch confusion problem at the source. Additionally, use `Closes #N` in all PR descriptions to auto-close issues on merge.

---

*Next retro scheduled after Phase 5 Wave 1 completes.*
