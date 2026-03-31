# Pipeline Operations Guide

This document describes the full data ingestion pipeline, its stages, dependencies, and operational procedures.

## Pipeline Overview

The pipeline ingests hadith data from 8+ sources, resolves narrator entities, loads a Neo4j graph, and enriches it with metrics, topics, and historical overlays. The stages run sequentially.

```
acquire -> parse -> validate-staging -> resolve -> load -> enrich
                                          |          |        |
                                     (CPU heavy)  (Neo4j)  (Neo4j)
```

## Stages

### 1. Acquire (`isnad acquire`)

Downloads raw data from all configured sources into `data/raw/`.

- **Sources:** Sunnah.com API, LK dataset, Sanadset, Fawaz, Open Hadith, Thaqalayn, Kaggle narrator bios, Wikipedia historical timeline
- **Requirements:** Network access. `SUNNAH_API_KEY` and `KAGGLE_USERNAME`/`KAGGLE_KEY` environment variables for their respective sources.
- **External services:** None (network only)
- **Idempotent:** Yes -- re-running downloads only missing or outdated files
- **Typical duration:** 10-30 minutes depending on network

### 2. Parse (`isnad parse`)

Parses raw data into normalized Parquet files in `data/staging/`.

- **Input:** `data/raw/` files (CSV, JSON, HTML)
- **Output:** `data/staging/hadiths_*.parquet`, `data/staging/narrators_bio_*.parquet`, `data/staging/historical_events.parquet`
- **External services:** None
- **Idempotent:** Yes

### 3. Validate Staging (`isnad validate-staging`)

Validates staging Parquet files against expected schemas and row count baselines.

- **External services:** None
- **Modes:** `--strict` (halt on failure) or warn mode (default)
- **Output:** Optional JSON report via `--output-json`

### 4. Resolve (`isnad resolve`)

Runs entity resolution: NER extraction, narrator disambiguation, and hadith deduplication.

- **Sub-stages:**
  - **NER:** Extracts narrator mentions from hadith texts, produces `narrator_mentions_resolved.parquet`
  - **Disambiguate:** 5-stage matching (exact, fuzzy, temporal, geographic, cross-reference) using blocking indexes. Produces `narrators_canonical.parquet`, `ambiguous_narrators.csv`, `merge_log.parquet`
  - **Dedup:** Generates sentence-transformer embeddings, builds FAISS index, identifies parallel hadith pairs. Produces `parallel_links.parquet`
- **External services:** None
- **Compute:** CPU-intensive (dedup benefits from GPU). Disambiguate uses blocking indexes to handle 3M+ mentions in <30min and <4GB memory.
- **Dependencies:** `ml` dependency group (`uv sync --group ml` for `sentence-transformers`, `faiss-cpu`)

### 5. Load (`isnad load`)

Loads resolved data into Neo4j.

- **Requires:** Running Neo4j instance (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`)
- **Node types:** NARRATOR, HADITH, COLLECTION, CHAIN, GRADING, HISTORICAL_EVENT, LOCATION
- **Edge types:** TRANSMITTED_TO, NARRATED, APPEARS_IN, PARALLEL_OF, ACTIVE_DURING, STUDIED_UNDER
- **Options:** `--incremental` (only load changed Parquet files), `--nodes-only`, `--skip-validation`

### 6. Enrich (`isnad enrich`)

Computes graph metrics, topic classification, and historical overlays.

- **Requires:** Running Neo4j instance with loaded graph
- **Sub-stages:**
  - **Metrics:** Betweenness centrality, PageRank, Louvain community detection
  - **Topics:** Hadith topic classification (requires `transformers` library)
  - **Historical:** Links narrators and compilers to historical events via `ACTIVE_DURING` edges
- **Options:** `--only metrics topics historical`, `--skip metrics`, `--incremental`

## Running the Pipeline

### Quick run (Makefile)

```bash
# Full pipeline (simple, no error recovery)
make pipeline

# Full pipeline with orchestration, logging, and flags
make pipeline-full
```

### Orchestrated run (recommended for production)

```bash
# Full run with logging to data/logs/
bash scripts/run_full_pipeline.sh

# Skip acquire (reuse existing raw data)
bash scripts/run_full_pipeline.sh --skip-acquire

# Skip resolve (reuse existing resolved entities)
bash scripts/run_full_pipeline.sh --skip-resolve

# Skip enrich (just load the graph, enrich later)
bash scripts/run_full_pipeline.sh --skip-enrich

# Dry run (show what would execute)
bash scripts/run_full_pipeline.sh --dry-run

# Custom per-source acquire timeout (default: 600s)
ACQUIRE_TIMEOUT=1200 bash scripts/run_full_pipeline.sh
```

### Partial re-runs

Common scenarios for partial pipeline execution:

| Scenario | Command |
|----------|---------|
| New raw data, re-parse only | `make parse` |
| Re-resolve with existing staging data | `make resolve` |
| Reload graph after resolve | `make load` |
| Re-enrich only metrics | `uv run isnad enrich --only metrics` |
| Incremental load (changed files only) | `uv run isnad load --incremental` |
| Full pipeline, skip slow acquire | `bash scripts/run_full_pipeline.sh --skip-acquire` |

### Pipeline audit

Every load and enrich run writes an audit entry. View recent entries:

```bash
uv run isnad audit --last 10
```

## Infrastructure Requirements

| Stage | Neo4j | PostgreSQL | Network | GPU |
|-------|-------|------------|---------|-----|
| acquire | - | - | Required | - |
| parse | - | - | - | - |
| validate-staging | - | - | - | - |
| resolve | - | - | - | Optional (dedup) |
| load | Required | - | - | - |
| enrich | Required | - | - | - |

Start infrastructure services before load/enrich:

```bash
make infra        # Start Neo4j, PostgreSQL, Redis via Docker Compose
make infra-down   # Stop services
make infra-reset  # Stop and destroy volumes
```

## Data Flow

```
data/raw/               <- acquire output (CSV, JSON, HTML)
  bukhari_*.json
  muslim_*.json
  ...
data/staging/           <- parse output (Parquet)
  hadiths_bukhari.parquet
  hadiths_muslim.parquet
  narrators_bio_kaggle.parquet
  historical_events.parquet
  narrator_mentions_resolved.parquet  <- NER output
  narrators_canonical.parquet         <- disambiguate output
  ambiguous_narrators.csv             <- disambiguate report
  merge_log.parquet                   <- disambiguate audit
  parallel_links.parquet              <- dedup output
  hadith_embeddings.npy               <- dedup embeddings
  hadith_embeddings.faiss             <- dedup FAISS index
data/curated/           <- resolve canonical output
```

## Troubleshooting

### Disambiguate produces no output

Check that NER has produced `narrator_mentions_resolved.parquet` and that biographical Parquet files (`narrators_bio_*.parquet`) exist in staging.

### Dedup skipped (missing deps)

Install the ML dependency group: `uv sync --group ml`. This provides `sentence-transformers`, `faiss-cpu`, and `transformers`.

### Load fails with Neo4j connection error

Verify Neo4j is running (`make infra`) and `.env` has correct `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`.

### Pipeline logs

Logs are written to `data/logs/` with timestamps. Each stage gets a separate log file when using `scripts/run_full_pipeline.sh`.
