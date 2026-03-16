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

## Quick Start

```bash
git clone git@github.com:parametrization/isnad-graph.git
cd isnad-graph
make setup    # Install dependencies with uv
make infra    # Start Neo4j, PostgreSQL, Redis via Docker Compose
make test     # Run test suite
```

Copy `.env.example` to `.env` and configure database credentials and API keys before running the pipeline.

To run the API and frontend:

```bash
uvicorn src.api.app:create_app --factory --reload  # Start FastAPI backend
cd frontend && npm install && npm run dev           # Start React frontend
```

See `docs/hadith-analysis-platform-prd.md` for full configuration details.

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
│   ├── acquire/            # Phase 1: data downloaders → data/raw/
│   ├── parse/              # Phase 1: parsers → data/staging/ (Parquet)
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
