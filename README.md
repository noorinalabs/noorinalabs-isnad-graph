# isnad-graph: Computational Hadith Analysis Platform

A computational hadith analysis platform that ingests Sunni and Shia hadith collections into a Neo4j graph database for isnad (chain of narration) analysis, narrator network topology, and cross-sectarian parallel detection. The platform combines graph-based chain modeling with vector similarity search to enable scholarly research across the major hadith corpora.

## Architecture Overview

| Component | Technology | Role |
|-----------|-----------|------|
| Graph Database | **Neo4j 5.x** | Isnad chains, narrator networks, transmission relationships |
| Relational Store | **PostgreSQL 16+ with pgvector** | Metadata, vector embeddings for semantic similarity |
| Cache | **Redis** | API response caching |
| Language | **Python 3.14+** | ETL pipeline, graph algorithms, API |
| API | **FastAPI** | REST endpoints for querying the graph |
| Frontend | **React + TypeScript** | Interactive narrator network visualization (D3.js) |

**Graph schema nodes:** `NARRATOR`, `HADITH`, `COLLECTION`, `CHAIN`, `GRADING`, `HISTORICAL_EVENT`, `LOCATION`

**Key relationships:** `TRANSMITTED_TO`, `NARRATED`, `APPEARS_IN`, `STUDIED_UNDER`, `PARALLEL_OF`

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.14+ | `python --version` |
| uv | latest | `uv --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Docker | 24+ | `docker --version` |
| Docker Compose | 2.0+ | `docker compose version` |
| Git | 2.0+ | `git --version` |

## Quick Start

### 1. Clone and install

```bash
git clone git@github.com:parametrization/isnad-graph.git
cd isnad-graph
make setup          # Install Python deps with uv
make setup-hooks    # Configure git hooks
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env -- see Environment Configuration below
```

For local development, the defaults in `.env.example` work out of the box with Docker Compose.

### 3. Start infrastructure

```bash
make infra          # Starts Neo4j, PostgreSQL, Redis via Docker Compose
```

### 4. Run the backend API

```bash
uvicorn src.api.app:create_app --factory --reload --port 8000
```

### 5. Run the frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev         # Starts on http://localhost:3000
```

### 6. Verify setup

```bash
curl http://localhost:8000/          # API health check
open http://localhost:3000           # Frontend
open http://localhost:7474           # Neo4j Browser
```

See the [Verify Your Setup](#verify-your-setup) section below for a full checklist.

## Environment Configuration

Copy `.env.example` to `.env` and configure:

### Required (infrastructure -- defaults work for local dev)

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt protocol URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `isnad_graph_dev` | Neo4j password |
| `PG_DSN` | `postgresql://isnad:isnad_dev@localhost:5432/isnad_graph` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL |

### Optional (data sources)

| Variable | Default | Description |
|----------|---------|-------------|
| `SUNNAH_API_KEY` | *(empty)* | Sunnah.com API key -- skip if unavailable |
| `KAGGLE_USERNAME` | *(empty)* | Kaggle credentials for Sanadset download |
| `KAGGLE_KEY` | *(empty)* | Kaggle API key |

### Optional (paths)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_RAW_DIR` | `./data/raw` | Downloaded source files |
| `DATA_STAGING_DIR` | `./data/staging` | Normalized Parquet intermediates |
| `DATA_CURATED_DIR` | `./data/curated` | Final enriched datasets |

### Optional (auth -- needed for OAuth login)

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_JWT_SECRET` | `dev-secret-change-in-production` | JWT signing secret |
| `AUTH_GOOGLE_CLIENT_ID` | *(empty)* | Google OAuth client ID |
| `AUTH_GOOGLE_CLIENT_SECRET` | *(empty)* | Google OAuth secret |
| `AUTH_GITHUB_CLIENT_ID` | *(empty)* | GitHub OAuth client ID |
| `AUTH_GITHUB_CLIENT_SECRET` | *(empty)* | GitHub OAuth secret |
| `AUTH_APPLE_CLIENT_ID` | *(empty)* | Apple OAuth client ID |
| `AUTH_APPLE_CLIENT_SECRET` | *(empty)* | Apple OAuth secret |
| `AUTH_FACEBOOK_CLIENT_ID` | *(empty)* | Facebook OAuth client ID |
| `AUTH_FACEBOOK_CLIENT_SECRET` | *(empty)* | Facebook OAuth secret |

### Optional (application)

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `["http://localhost:3000"]` | JSON list of allowed CORS origins |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FORMAT` | `console` | Log format (`console` or `json`) |

For local development, the infrastructure defaults work out of the box. OAuth keys are only needed if testing login flows.

## Port Reference

| Service | Port | URL |
|---------|------|-----|
| Frontend (Vite) | 3000 | http://localhost:3000 |
| Backend API | 8000 | http://localhost:8000 |
| API Docs (Swagger) | 8000 | http://localhost:8000/docs |
| API Docs (ReDoc) | 8000 | http://localhost:8000/redoc |
| Neo4j Browser | 7474 | http://localhost:7474 |
| Neo4j Bolt | 7687 | bolt://localhost:7687 |
| PostgreSQL | 5432 | -- |
| Redis | 6379 | -- |

## Phase Overview

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Scaffold & Tooling | :white_check_mark: |
| 1 | Data Acquisition & Parsing | :white_check_mark: |
| 2 | Entity Resolution | :white_check_mark: |
| 3 | Graph Loading | :white_check_mark: |
| 4 | Enrichment & Metrics | :white_check_mark: |
| 5 | API & Frontend | :white_check_mark: |
| 6 | Testing, CI/CD & Hardening | :white_check_mark: |

## API

The REST API is built with FastAPI and exposes the graph data for querying.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check (Neo4j connectivity) |
| GET | `/api/v1/narrators` | Paginated narrator list |
| GET | `/api/v1/narrators/{id}` | Single narrator by ID |
| GET | `/api/v1/hadiths` | Paginated hadith list |
| GET | `/api/v1/hadiths/{id}` | Single hadith by ID |
| GET | `/api/v1/collections` | All collections |
| GET | `/api/v1/collections/{id}` | Single collection by ID |
| GET | `/api/v1/graph/narrator/{id}/chains` | Isnad chains through a narrator |
| GET | `/api/v1/graph/hadith/{id}/chain` | Chain visualization for a hadith |
| GET | `/api/v1/graph/narrator/{id}/network` | Narrator ego network (teachers/students) |
| GET | `/api/v1/search?q=...` | Full-text search across narrators and hadiths |
| GET | `/api/v1/search/semantic?q=...` | Semantic search (pgvector, coming soon) |
| GET | `/api/v1/parallels/{id}` | Cross-sectarian parallel hadiths |
| GET | `/api/v1/timeline` | Historical timeline entries |

**Run the API:**

```bash
uvicorn src.api.app:create_app --factory --reload
```

## Frontend

The frontend is a React + TypeScript application with interactive narrator network visualizations powered by D3.js.

**Run the frontend:**

```bash
cd frontend && npm install && npm run dev
```

## Docker Services

Start all infrastructure (Neo4j, PostgreSQL, Redis):

```bash
make infra
```

Stop services:

```bash
make infra-down
```

Reset (stop services and destroy volumes):

```bash
make infra-reset
```

Full stack via Docker Compose (API + frontend + infrastructure):

```bash
docker compose up -d
```

## Verify Your Setup

After following Quick Start, confirm everything is working:

1. `curl http://localhost:8000/` -- should return `{"status": "ok", ...}`
2. Open http://localhost:3000 -- should see the isnad-graph frontend
3. Open http://localhost:7474 -- Neo4j Browser (login: `neo4j` / `isnad_graph_dev`)
4. `make test` -- should pass all unit tests
5. `make check` -- should pass lint + typecheck + test

## Data Sources

| Source | Format | Coverage |
|--------|--------|----------|
| LK Dataset | CSV | Large Sunni collection with isnad markup |
| SanadSet | Parquet | Parsed isnad chains |
| Thaqalayn | REST API | Shia hadith collections |
| Sunnah.com | REST API | Major Sunni collections (Bukhari, Muslim, etc.) |
| Fawaz Ahmed | JSON | Multi-language hadith translations |
| Open Hadith Data | JSON | Cleaned hadith datasets |
| Muhaddithat | CSV | Female narrator biographical data |

## Directory Structure

```
isnad-graph/
├── src/                    # Application source code
│   ├── acquire/            # Phase 1: data downloaders -> data/raw/
│   ├── parse/              # Phase 1: parsers -> data/staging/ (Parquet)
│   ├── resolve/            # Phase 2: narrator NER/disambiguation, hadith dedup
│   ├── graph/              # Phase 3: Neo4j node/edge loaders
│   ├── enrich/             # Phase 4: graph metrics, topic classification
│   ├── models/             # Frozen Pydantic v2 models (nodes & edges)
│   ├── api/               # Phase 5: FastAPI app, routes, response models
│   ├── utils/              # Arabic text processing, DB clients, logging
│   ├── config.py           # Pydantic Settings (loads .env)
│   └── cli.py              # CLI entry point (`isnad` command)
├── frontend/               # React + TypeScript frontend (Vite)
├── data/
│   ├── raw/                # Downloaded source files
│   ├── staging/            # Normalized Parquet intermediates
│   └── curated/            # Final enriched datasets
├── tests/                  # Test suite (pytest)
│   ├── test_models/
│   └── test_utils/
├── docs/                   # PRD, phase specs, Mermaid diagrams
├── queries/                # Cypher queries
│   ├── analysis/           # Analytical queries
│   └── validation/         # Data validation queries
├── notebooks/              # Jupyter notebooks for exploration
├── docker-compose.yml      # Neo4j, PostgreSQL, Redis services
├── Makefile                # Build, test, pipeline commands
└── pyproject.toml          # Project metadata & dependencies (uv)
```

## Makefile Targets

| Target | Description |
|--------|-------------|
| `help` | Show all targets with descriptions |
| `setup` | Install dependencies with uv |
| `setup-hooks` | Configure git hooks |
| `infra` | Start Docker services (Neo4j, PostgreSQL, Redis) |
| `infra-down` | Stop Docker services |
| `infra-reset` | Stop services and destroy volumes |
| `test` | Run pytest suite |
| `test-integration` | Run integration tests (requires Docker) |
| `test-e2e` | Run Playwright browser tests (requires running app) |
| `test-e2e-headed` | Run Playwright tests with visible browser |
| `sample-data` | Download sample data for integration testing |
| `lint` | Run ruff linter |
| `format` | Run ruff formatter |
| `typecheck` | Run mypy type checker |
| `check` | Run all CI checks locally (lint + typecheck + test) |
| `acquire` | Phase 1: Download all data sources |
| `parse` | Phase 1: Parse raw data into staging Parquet files |
| `resolve` | Phase 2: Entity resolution (NER + disambiguation + dedup) |
| `load` | Phase 3: Load graph into Neo4j |
| `enrich` | Phase 4: Compute metrics, topics, historical overlay |
| `pipeline` | Run full end-to-end pipeline (acquire through enrich) |
| `validate-staging` | Validate staging Parquet files |
| `validate-pipeline` | Run full pipeline validation against real data |
| `profile-data` | Profile staging Parquet files |
| `clean` | Remove staging data and caches |
| `clean-worktrees` | Remove stale git worktrees |

## Testing

```bash
make test              # Run unit tests (pytest)
make test-integration  # Run integration tests (requires Docker services)
make test-e2e          # Run Playwright browser tests (requires running app)
make test-e2e-headed   # Run Playwright tests with visible browser
```

## Development

```bash
make lint        # Run ruff linter
make format      # Run ruff formatter
make typecheck   # Run mypy in strict mode
make clean       # Remove staging data and caches
```

Run the full ETL pipeline or individual phases:

```bash
make pipeline    # Full end-to-end pipeline
make acquire     # Phase 1: download raw data
make parse       # Phase 1: parse to staging Parquet
make resolve     # Phase 2: entity resolution
make load        # Phase 3: load into Neo4j
make enrich      # Phase 4: compute metrics & topics
```

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
