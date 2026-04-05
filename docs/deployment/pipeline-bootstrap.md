# Pipeline Bootstrap Runbook — One-Time VPS Data Population

This runbook documents the one-time bootstrap procedure to populate the production
Neo4j database on the VPS with narrator nodes, grades, topics, and historical events.

> **Context:** Issue #668. Until the automated CI pipeline is built, this manual
> bootstrap is the sanctioned path. The manifest files (#598) track what was loaded,
> so future updates go through the automated pipeline.

## Prerequisites

| Requirement | Check |
|-------------|-------|
| SSH access to VPS | `ssh deploy@<VPS_HOST> echo ok` |
| `.env` populated on VPS | All `[REQUIRED]` vars from `.env.example` set |
| Docker services running | `docker compose ps` shows neo4j, postgres, redis healthy |
| Python 3.14+ with uv | `uv --version` |
| ML dependencies installed | `uv sync --group ml` |
| Staging data present | `ls data/staging/*.parquet \| wc -l` >= 15 |
| API keys configured | `SUNNAH_API_KEY`, `KAGGLE_USERNAME`, `KAGGLE_KEY` in `.env` |

## Quick Start

For operators who just want to run the pipeline:

```bash
ssh deploy@<VPS_HOST>
cd /opt/isnad-graph
bash scripts/run_full_pipeline.sh --generate-manifest 2>&1 | tee data/logs/bootstrap_$(date +%Y%m%d).log
```

## Detailed Steps

### 1. Connect and Set Up Environment

```bash
ssh deploy@<VPS_HOST>
cd /opt/isnad-graph

# Load environment variables
set -a; source .env; set +a

# Verify environment
echo "NEO4J_URI=$NEO4J_URI"
echo "ENVIRONMENT=${ENVIRONMENT:-development}"
```

### 2. Install ML Dependencies

The resolve stage requires `sentence-transformers`, `faiss-cpu`, and `camel-tools`.

```bash
uv sync --group ml
```

If the VPS has limited RAM (<4GB), set swap first:

```bash
# Check existing swap
free -h

# If no swap, create 4GB (requires root)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### 3. Verify Staging Data

```bash
ls data/staging/*.parquet | wc -l
# Expected: 15+ files

# Quick profile
uv run python scripts/data_profile.py
```

If staging data is missing, run acquire + parse first:

```bash
bash scripts/run_full_pipeline.sh --skip-resolve --skip-load --skip-enrich
```

### 4. Run the Full Pipeline

The recommended approach uses the pipeline script with all stages:

```bash
ENVIRONMENT=production bash scripts/run_full_pipeline.sh --generate-manifest 2>&1 \
  | tee data/logs/bootstrap_$(date +%Y%m%d).log
```

Or use the Makefile shortcut:

```bash
make pipeline-bootstrap
```

For stage-by-stage control:

```bash
# Stage 1: Acquire raw data (~10 min)
ENVIRONMENT=production uv run isnad acquire 2>&1 | tee data/logs/acquire_$(date +%Y%m%d).log

# Stage 2: Parse to staging Parquet (~5 min)
ENVIRONMENT=production uv run isnad parse 2>&1 | tee data/logs/parse_$(date +%Y%m%d).log

# Stage 3: Validate staging
ENVIRONMENT=production uv run isnad validate-staging

# Stage 4: Entity resolution (~30-60 min, CPU intensive)
ENVIRONMENT=production uv run isnad resolve 2>&1 | tee data/logs/resolve_$(date +%Y%m%d).log

# Stage 5: Load into Neo4j (~5 min)
ENVIRONMENT=production uv run isnad load 2>&1 | tee data/logs/load_$(date +%Y%m%d).log

# Stage 6: Enrichment — metrics, topics, historical overlay (~10 min)
ENVIRONMENT=production uv run isnad enrich 2>&1 | tee data/logs/enrich_$(date +%Y%m%d).log
```

### 5. Generate and Save Manifest

If you ran with `--generate-manifest`, this is already done. Otherwise:

```bash
uv run python scripts/generate_manifest.py
cp data/.manifest.json data/.last_loaded_manifest.json
```

### 6. Verify Results

#### Neo4j Cypher Checks

```bash
# Connect to Neo4j
docker compose exec neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD"
```

```cypher
// Narrator count (expect 10,000+)
MATCH (n:NARRATOR) RETURN count(n);

// Hadith count (expect 50,000+)
MATCH (h:HADITH) RETURN count(h);

// Chain count
MATCH (c:CHAIN) RETURN count(c);

// Grades populated
MATCH (h:HADITH)-[:HAS_GRADING]->(g:GRADING) RETURN count(g);

// Topics populated
MATCH (h:HADITH) WHERE h.topics IS NOT NULL RETURN count(h);

// Historical events
MATCH (e:HISTORICAL_EVENT) RETURN count(e);

// Network connectivity — narrator transmission links
MATCH ()-[r:TRANSMITTED_TO]->() RETURN count(r);
```

#### Application Checks

- [ ] Narrators page shows data (`/narrators`)
- [ ] Graph Explorer shows network visualization (`/explorer`)
- [ ] Hadiths have grades and topics (`/hadiths/<id>`)
- [ ] Search returns results (`/search?q=bukhari`)

### 7. Post-Bootstrap Cleanup

```bash
# Archive logs
tar czf data/logs/bootstrap_$(date +%Y%m%d).tar.gz data/logs/*_$(date +%Y%m%d)*.log

# Verify manifest is saved
cat data/.manifest.json | python3 -m json.tool | head -20
```

## VPS-Side Only: Load + Enrich After B2 Download

If staging/curated data has already been downloaded from B2, run only the load and
enrich stages:

```bash
make pipeline-load
# or:
ENVIRONMENT=production bash scripts/run_full_pipeline.sh --only-load --generate-manifest
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| OOM during resolve | Increase swap (step 2), check `docker stats`, reduce batch size via `RESOLVE_BATCH_SIZE` env var |
| `sentence-transformers` missing | Re-run `uv sync --group ml` |
| Neo4j connection refused | Check `docker compose ps`, verify `NEO4J_URI` in `.env` |
| Neo4j GDS unavailable | Metrics that require GDS are skipped gracefully — not blocking |
| Parse fails on missing raw data | Run `uv run isnad acquire` first |
| Slow resolve (~2h+) | Expected on 2-core VPS; consider running on CI runner instead |
| Disk full | Check `df -h`, prune Docker: `docker system prune -f` |

## Architecture Note

This bootstrap is a one-time operation. The target architecture is:

```
CI runner (acquire/parse/resolve) --> B2 storage --> VPS (load/enrich)
```

Follow-up issues track the automation work needed to reach this target state.
