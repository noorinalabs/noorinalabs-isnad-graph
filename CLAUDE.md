# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**isnad-graph** is a computational hadith analysis platform that ingests Sunni and Shia hadith collections into a Neo4j graph database for isnad (chain of narration) analysis, narrator network topology, and cross-sectarian parallel detection. The project is implemented in 5 phases (see `docs/` for detailed specs).

## Tech Stack

- **Python 3.14.3** with **uv** as the package manager
- **Neo4j 5.x** — primary graph database (isnad chains, narrator networks)
- **PostgreSQL 16+ with pgvector** — relational metadata, vector embeddings for semantic similarity
- **Redis** — optional API response caching
- **FastAPI** (API layer, Phase 5) / **React + TypeScript** (frontend, Phase 5)
- **Docker Compose** for infrastructure services

## Build & Development Commands

```bash
make setup          # Install dependencies with uv
make infra          # Start Docker services (Neo4j, PostgreSQL, Redis)
make infra-down     # Stop Docker services
make infra-reset    # Stop and remove volumes

make test           # Run all tests
make lint           # Run ruff linter
make format         # Run ruff formatter
make typecheck      # Run mypy (strict mode)

make pipeline       # Run full ETL pipeline end-to-end
make acquire        # Phase 1: download raw data
make parse          # Phase 1: parse to staging Parquet
make resolve        # Phase 2: entity resolution
make load           # Phase 3: load into Neo4j
make enrich         # Phase 4: compute metrics & topics
make clean          # Remove staging data
```

**CLI entry point:** `isnad` (defined in `[project.scripts]` as `src.cli:main`)

## Architecture

### Monorepo layout under `src/`

| Module | Phase | Purpose |
|--------|-------|---------|
| `models/` | 0 | Frozen Pydantic v2 models for all graph nodes and edges |
| `utils/` | 0 | Arabic text processing, Neo4j/PG clients, structured logging |
| `config.py` | 0 | Pydantic Settings (loads `.env`), singleton via `get_settings()` |
| `acquire/` | 1 | Downloaders for 7+ data sources → `data/raw/` |
| `parse/` | 1 | Parsers producing normalized Parquet → `data/staging/` |
| `resolve/` | 2 | Narrator NER/disambiguation, hadith dedup (CAMeLBERT, FAISS) |
| `graph/` | 3 | Neo4j node/edge loaders, validation queries |
| `enrich/` | 4 | Graph metrics (centrality, PageRank, Louvain), topic classification |

### Graph Schema (Neo4j)

**Nodes:** NARRATOR, HADITH, COLLECTION, CHAIN, GRADING, HISTORICAL_EVENT, LOCATION

**Key relationships:** TRANSMITTED_TO (narrator→narrator), NARRATED (narrator→hadith), APPEARS_IN (hadith→collection), STUDIED_UNDER (narrator→narrator), PARALLEL_OF (hadith↔hadith)

### Data flow

Raw sources (CSV, JSON, REST APIs) → `data/raw/` → parsers → `data/staging/` (Parquet) → entity resolution → Neo4j graph + PostgreSQL metadata

## Code Conventions

- **Ruff** for linting and formatting, line length 100, with isort/pyflakes/pycodestyle/pydantic rules enabled
- **mypy** strict mode with pydantic plugin
- All Pydantic models use `ConfigDict(frozen=True)` for immutability
- All enums are `(str, Enum)` for clean JSON/Parquet serialization
- All downloaders and loaders must be **idempotent** (safe to re-run)
- Arabic text utilities are pure Python (no NLP deps in Phase 0): diacritics stripping, alif/hamza/taa marbuta normalization, transmission phrase extraction
- Staging data uses PyArrow schemas as intermediate between raw data and graph nodes

## Configuration

Copy `.env.example` to `.env`. Key variables:
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` — graph database
- `PG_DSN` — PostgreSQL connection string
- `SUNNAH_API_KEY` — required for Sunnah.com API
- `KAGGLE_USERNAME`, `KAGGLE_KEY` — required for Kaggle datasets
- `DATA_RAW_DIR`, `DATA_STAGING_DIR`, `DATA_CURATED_DIR` — data paths

## Team Workflow

**All work MUST be executed through the simulated team structure.** No work begins without spawning the team.

- **Charter & rules:** `.claude/team/charter.md`
- **Active roster:** `.claude/team/roster/` (one file per team member with persistent name and personality)
- **Feedback log:** `.claude/team/feedback_log.md`

### Team Composition
| Role | Level | Name | File |
|------|-------|------|------|
| Manager | Senior VP (Executive) | Fatima Okonkwo | `roster/manager_fatima.md` |
| System Architect | Partner | Renaud Tremblay | `roster/architect_renaud.md` |
| DevOps Architect | Staff | Sunita Krishnamurthy | `roster/devops_architect_sunita.md` |
| DevOps Engineer | Senior | Tomasz Wójcik | `roster/devops_engineer_tomasz.md` |
| Tech Lead | Staff | Dmitri Volkov | `roster/tech_lead_dmitri.md` |
| Engineer | Principal | Kwame Asante | `roster/engineer_kwame.md` |
| Engineer | Senior | Amara Diallo | `roster/engineer_amara.md` |
| Engineer | Senior | Hiro Tanaka | `roster/engineer_hiro.md` |
| Engineer | Senior | Carolina Méndez-Ríos | `roster/engineer_carolina.md` |
| Security Engineer | Senior | Yara Hadid | `roster/security_engineer_yara.md` |
| QA Engineer | Senior | Priya Nair | `roster/qa_engineer_priya.md` |
| Data Engineer (Lead) | Staff | Elena Petrova | `roster/data_lead_elena.md` |
| Data Engineer | Senior | Rashid Osei-Mensah | `roster/data_engineer_rashid.md` |
| Data Scientist | Principal | Mei-Lin Chang | `roster/data_scientist_mei.md` |
| UX Designer | Principal | Sable Nakamura-Whitfield | `roster/ux_designer_sable.md` |

### Key Rules
- **Commit identity:** Each team member commits using per-commit `-c` flags with their name and `parametrization+{FirstName}.{LastName}@gmail.com` email — **never** set global/repo git config. See `.claude/team/charter.md` § Commit Identity for the full table.
- **Worktrees** are the preferred isolation method for all code-writing agents
- Manager spawns team members, creates stories/AC from PRD, and owns timelines
- Manager, System Architect, and DevOps Engineer coordinate to prevent cross-team blocking
- Feedback flows up and down; severe feedback triggers fire-and-replace
- If the Manager receives significant negative feedback from the user, the Manager is replaced
- Team evolves toward steady state of minimal negative feedback

## Developer Tooling & Orchestration

- **gh-cli** is installed and available from the terminal
- **SSH access** is enabled from the terminal
- **GitHub Projects** — project/feature tracking and board management
- **GitHub Issues** — story/task/bug tracking (created by Manager, assigned to team members)
- **GitHub Actions** — CI/CD pipelines, automated tests, linting, deployment
- These three (Projects, Issues, Actions) are the **core orchestration layer** — do not introduce alternative tools for these concerns
- **Branching strategy:** Feature branches named `{FirstInitial}.{LastName}\{IIII}-{issue-name}` (e.g., `F.Okonkwo\0042-setup-docker-compose`) merged to `main` via PR

## Key Documentation

- `docs/hadith-analysis-platform-prd.md` — full PRD with schema details, data sources, risk register
- `docs/phase0-claude-code-instructions.md` — Phase 0 scaffold spec
- `docs/phase1-claude-code-instructions.md` — Phase 1 acquisition & parsing spec
- `docs/diagrams/` — Mermaid diagrams (entity relationships, system architecture, Gantt chart)
