# isnad-graph: Computational Hadith Analysis Platform

A computational hadith analysis platform that ingests Sunni and Shia hadith collections into a Neo4j graph database for isnad (chain of narration) analysis, narrator network topology, and cross-sectarian parallel detection. The platform combines graph-based chain modeling with vector similarity search to enable scholarly research across the major hadith corpora.

## Architecture Overview

| Component | Technology | Role |
|-----------|-----------|------|
| Graph Database | **Neo4j 5.x** | Isnad chains, narrator networks, transmission relationships |
| Relational Store | **PostgreSQL 16+ with pgvector** | Metadata, vector embeddings for semantic similarity |
| Cache | **Redis** | API response caching |
| Language | **Python 3.14+** | ETL pipeline, graph algorithms, API |
| API (Phase 5) | **FastAPI** | REST/GraphQL endpoints for querying the graph |
| Frontend (Phase 5) | **React + TypeScript** | Interactive narrator network visualization |

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

Copy `.env.example` to `.env` and configure database credentials and API keys before running the pipeline. See `docs/hadith-analysis-platform-prd.md` for full configuration details.

## Phase Overview

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Scaffold & Tooling | :white_check_mark: |
| 1 | Data Acquisition & Parsing | :white_check_mark: |
| 2 | Entity Resolution | :white_check_mark: |
| 3 | Graph Loading | :white_large_square: |
| 4 | Enrichment & Metrics | :white_large_square: |
| 5 | API & Frontend | :white_large_square: |

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
│   ├── utils/              # Arabic text processing, DB clients, logging
│   ├── config.py           # Pydantic Settings (loads .env)
│   └── cli.py              # CLI entry point (`isnad` command)
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

## Development

```bash
make lint        # Run ruff linter
make format      # Run ruff formatter
make typecheck   # Run mypy in strict mode
make test        # Run pytest suite
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

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
