# Hadith Analysis Platform — Product Requirements Document

> **Implementation status (2026-03-15):** Phases 0 through 6 are fully implemented. See the README for current architecture and usage instructions.

**Codename:** `isnad-graph`
**Version:** 0.1.0-draft
**Date:** 2026-03-13

---

## 1. Vision & Objectives

Build a computational hadith analysis platform that treats the Islamic hadith corpus as a graph-theoretic and historiographic dataset. The platform ingests, normalizes, and unifies Sunni and Shia hadith collections into a queryable graph database, enabling:

- **Isnad topology analysis** — common ancestral chains, transmission bottlenecks (madār narrators), chain completeness, and structural anomalies.
- **Narrator-centric analytics** — transmission volume, temporal distribution, geographic footprint, teacher-student networks, and trustworthiness cross-referencing.
- **Political and historical milieu correlation** — overlay of caliphal timelines, fitna periods, and regional power structures onto hadith circulation patterns.
- **Sunni-Shia intersectionality** — parallel hadith detection across sectarian boundaries, divergent chain comparison, and shared-narrator identification.

---

## 2. Data Sources

| Source | Type | Coverage | Format | Access |
|--------|------|----------|--------|--------|
| **LK Hadith Corpus** | Academic NLP corpus | 39K hadiths, Six Sunni Books | CSV (Isnad/Matn segmented) | GitHub: `ShathaTm/LK-Hadith-Corpus` |
| **Sanadset 650K** | Narrator-tagged corpus | 650K hadiths, 926 books | CSV with `<NAR>` tags | Kaggle: `fahd09/hadith-dataset` |
| **Narrator Bios (24K+)** | Biographical dataset | Narrators from Sihaah as-Sittah | Searchable DB / CSV | Kaggle: `fahd09/hadith-narrators` + `thehadith.co.uk` |
| **muhaddithat/isnad-datasets** | Network graph data | Female narrators, isnad CSVs | CSV + Jupyter Notebooks | GitHub: `muhaddithat/isnad-datasets` |
| **ThaqalaynAPI** | Shia hadith corpus | 20K+ ahadith, Imami collections | REST/GraphQL + JSON dump | `thaqalayn-api.net` + GitHub: `MohammedArab1/ThaqalaynAPI` |
| **fawazahmed0/hadith-api** | Multi-language hadith | Broad coverage, multi-grade | Static JSON via CDN | `cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/` |
| **Sunnah.com API** | Curated Sunni hadith | Primary + secondary collections | REST (API key required) | `api.sunnah.com/v1/` |
| **Open-Hadith-Data** | CSV with diacritics | 9 books, dual encoding | CSV (tashkeel + stripped) | GitHub: `mhashim6/Open-Hadith-Data` |

---

## 3. Architecture

### 3.1 Storage Layer

| Store | Purpose | Technology |
|-------|---------|------------|
| **Graph DB** | Primary: isnad chains, narrator networks, cross-references | Neo4j (Community or Aura) |
| **Relational DB** | Metadata, search indices, biographical records, gradings | PostgreSQL 16+ |
| **Vector Store** | Semantic similarity for matn dedup and parallel detection | pgvector extension on PostgreSQL (or Qdrant) |
| **Object Store** | Raw source files, ETL artifacts, backups | Local filesystem or S3-compatible |

### 3.2 Graph Schema

#### Node Types

```
NARRATOR
├── id: string (canonical, e.g., "nar:abu-hurayra-001")
├── name_ar: string
├── name_en: string
├── kunya: string
├── nisba: string
├── laqab: string
├── birth_year_ah: int (nullable)
├── death_year_ah: int (nullable)
├── birth_location_id: string (FK → LOCATION)
├── death_location_id: string (FK → LOCATION)
├── generation: enum [sahabi, tabii, taba_tabii, atba_taba_tabiin, later]
├── gender: enum [male, female]
├── sect_affiliation: enum [sunni, shia, neutral, unknown]
├── tabaqat_class: string
├── trustworthiness_consensus: enum [thiqa, saduq, daif, matruk, kadhdhab, unknown]
└── aliases: list<string>

HADITH
├── id: string (canonical, e.g., "hdt:bukhari-001-001")
├── matn_ar: string
├── matn_en: string
├── isnad_raw_ar: string
├── isnad_raw_en: string
├── grade_composite: string
├── topic_tags: list<string>
├── source_corpus: enum [lk, sanadset, thaqalayn, sunnah, fawaz, open_hadith]
├── has_shia_parallel: bool
├── has_sunni_parallel: bool
└── embedding_vector: float[] (768-dim, for semantic search)

COLLECTION
├── id: string (e.g., "col:bukhari")
├── name_ar: string
├── name_en: string
├── compiler_id: string (FK → NARRATOR, nullable)
├── compilation_year_ah: int
├── sect: enum [sunni, shia]
├── canonical_rank: int
├── total_hadiths: int
└── book_count: int

CHAIN
├── id: string (e.g., "chn:bukhari-001-001-0")
├── hadith_id: string (FK → HADITH)
├── chain_index: int (0-based, for hadiths with multiple chains)
├── full_chain_text_ar: string
├── full_chain_text_en: string
├── chain_length: int
├── is_complete: bool
├── is_elevated: bool (ali isnad = short chain)
└── classification: enum [muttasil, mursal, muallaq, munqati, mudallas]

GRADING
├── id: string
├── hadith_id: string (FK → HADITH)
├── scholar_name: string
├── grade: enum [sahih, hasan, daif, mawdu, sahih_li_ghayrihi, hasan_li_ghayrihi]
├── methodology_school: string
└── era: string

HISTORICAL_EVENT
├── id: string
├── name_en: string
├── name_ar: string
├── year_start_ah: int
├── year_end_ah: int
├── year_start_ce: int
├── year_end_ce: int
├── type: enum [caliphate, fitna, conquest, theological_controversy, compilation_effort]
├── caliphate: string
└── region: string

LOCATION
├── id: string
├── name_en: string
├── name_ar: string
├── region: string
├── lat: float
├── lon: float
└── political_entity_period: jsonb
```

#### Edge Types (Neo4j Relationships)

```
(NARRATOR)-[:TRANSMITTED_TO {
    hadith_id, chain_id, position_in_chain: int,
    transmission_method: enum [haddathana, akhbarana, sami'tu, an, qala, others]
}]->(NARRATOR)

(NARRATOR)-[:NARRATED {
    role: enum [originator, transmitter, compiler],
    chain_position: enum [first, middle, last]
}]->(HADITH)

(HADITH)-[:APPEARS_IN {
    book_number: int, chapter_number: int, hadith_number_in_book: int
}]->(COLLECTION)

(HADITH)-[:GRADED_BY]->(GRADING)

(NARRATOR)-[:STUDIED_UNDER {
    period_ah: string, location_id: string,
    source: string
}]->(NARRATOR)

(NARRATOR)-[:BASED_IN {
    period_ah: string, role: string
}]->(LOCATION)

(NARRATOR)-[:ACTIVE_DURING {
    role: string, affiliation: string
}]->(HISTORICAL_EVENT)

(HADITH)-[:PARALLEL_OF {
    similarity_score: float (0.0–1.0),
    variant_type: enum [verbatim, close_paraphrase, thematic, contradictory],
    cross_sect: bool
}]->(HADITH)

(CHAIN)-[:BELONGS_TO]->(HADITH)

(CHAIN)-[:HAS_LINK {
    position: int, from_narrator_id: string, to_narrator_id: string,
    transmission_method: string
}]->(CHAIN)  // self-referential for chain decomposition storage
```

### 3.3 ETL Pipeline

The pipeline is designed as a DAG (directed acyclic graph) of idempotent tasks.
Orchestration: Prefect, Airflow, or simple Makefile-based for Phase 1.

```
STAGE 1: ACQUIRE
  ├── download_lk_corpus()         → raw/lk/*.csv
  ├── download_sanadset()          → raw/sanadset/*.csv
  ├── download_narrator_bios()     → raw/narrators/*.csv
  ├── download_thaqalayn_dump()    → raw/thaqalayn/*.json
  ├── fetch_fawaz_editions()       → raw/fawaz/*.json
  ├── fetch_sunnah_api()           → raw/sunnah/*.json
  └── download_isnad_datasets()    → raw/muhaddithat/*.csv

STAGE 2: PARSE & NORMALIZE
  ├── parse_lk_corpus()
  │     Input: raw/lk/*.csv
  │     Output: staging/hadiths_lk.parquet, staging/isnads_lk.parquet
  │     Notes: Read with pandas, correct encoding. Map columns to canonical schema.
  │            Bukhari subset = gold standard. Others = 92% isnad segmentation accuracy.
  │
  ├── parse_sanadset()
  │     Input: raw/sanadset/*.csv
  │     Output: staging/hadiths_sanadset.parquet, staging/narrators_sanadset.parquet
  │     Notes: Extract <NAR>-tagged entities from isnad strings.
  │            ~160K records have no sanad — flag as matn_only.
  │
  ├── parse_thaqalayn()
  │     Input: raw/thaqalayn/*.json
  │     Output: staging/hadiths_shia.parquet
  │     Notes: JSON structure: book → chapter → hadith. Map grades where available.
  │
  ├── parse_narrator_bios()
  │     Input: raw/narrators/*.csv + thehadith.co.uk data
  │     Output: staging/narrators_bio.parquet
  │     Notes: Normalize names. Extract birth/death years. Map trustworthiness grades.
  │
  └── parse_supplementary()
        Input: raw/fawaz/*.json, raw/sunnah/*.json, raw/muhaddithat/*.csv
        Output: staging/hadiths_supplementary.parquet, staging/network_edges.parquet

STAGE 3: ENTITY RESOLUTION
  ├── narrator_ner()
  │     Input: staging/isnads_lk.parquet (raw isnad text)
  │     Output: staging/narrator_mentions.parquet
  │     Method: Arabic NER model (CAMeLBERT or custom fine-tuned) + rule-based
  │             extraction for patterned phrases (حدثنا, أخبرنا, عن, etc.)
  │
  ├── narrator_disambiguation()
  │     Input: staging/narrator_mentions.parquet + staging/narrators_bio.parquet
  │              + staging/narrators_sanadset.parquet
  │     Output: staging/narrators_canonical.parquet (deduplicated, ID-assigned)
  │     Method: Fuzzy string matching (arabic-reshaper + Levenshtein),
  │             temporal constraint satisfaction (overlapping lifetimes),
  │             cross-reference with muslimscholars.info IDs where available.
  │     Risk: This is the hardest NLP problem in the pipeline. Budget for iterative
  │            refinement and human-in-the-loop validation on high-ambiguity cases.
  │
  └── hadith_dedup()
        Input: staging/hadiths_*.parquet
        Output: staging/hadiths_canonical.parquet + staging/parallel_links.parquet
        Method: Sentence-transformer embeddings (e.g., `paraphrase-multilingual-MiniLM-L12-v2`)
                on matn_en. Cosine similarity > 0.85 = candidate parallel. Human review
                for cross-sect pairs. Store similarity scores on PARALLEL_OF edges.

STAGE 4: GRAPH CONSTRUCTION
  ├── build_narrator_nodes()
  │     Input: staging/narrators_canonical.parquet
  │     Output: Neo4j NARRATOR nodes
  │
  ├── build_hadith_nodes()
  │     Input: staging/hadiths_canonical.parquet
  │     Output: Neo4j HADITH nodes + PostgreSQL metadata rows
  │
  ├── build_chain_edges()
  │     Input: staging/narrator_mentions.parquet (resolved IDs)
  │     Output: Neo4j CHAIN nodes + TRANSMITTED_TO edges
  │     Method: For each hadith, decompose isnad into ordered narrator pairs.
  │             Create CHAIN node. Create TRANSMITTED_TO edge for each adjacent pair.
  │
  ├── build_collection_edges()
  │     Input: staging/hadiths_canonical.parquet (collection metadata)
  │     Output: Neo4j APPEARS_IN edges
  │
  ├── build_parallel_edges()
  │     Input: staging/parallel_links.parquet
  │     Output: Neo4j PARALLEL_OF edges
  │
  └── build_historical_overlay()
        Input: Manual/curated historical_events.yaml + narrator biographical dates
        Output: Neo4j ACTIVE_DURING edges, LOCATION nodes, BASED_IN edges

STAGE 5: INDEX & ENRICH
  ├── compute_embeddings()
  │     Input: Neo4j HADITH nodes (matn_en field)
  │     Output: pgvector embeddings table
  │
  ├── compute_graph_metrics()
  │     Input: Neo4j graph
  │     Output: Narrator node properties: betweenness_centrality, in_degree,
  │             out_degree, pagerank, community_id (Louvain)
  │
  └── topic_classification()
        Input: HADITH nodes (matn_en)
        Output: topic_tags property on HADITH nodes
        Method: Zero-shot NLI (e.g., `facebook/bart-large-mnli`) with candidate labels:
                [theology, jurisprudence, eschatology, succession, ritual,
                 ethics, history, commerce, warfare, family_law, etc.]
```

---

## 4. Implementation Phases

### Phase 0: Scaffold & Tooling (Week 1)

**Objective:** Repository structure, dependency management, local dev environment.

**Deliverables:**
- Monorepo structure: `isnad-graph/`
  ```
  isnad-graph/
  ├── README.md
  ├── pyproject.toml              # uv or poetry
  ├── Makefile                    # orchestration
  ├── docker-compose.yml          # Neo4j + PostgreSQL + pgvector
  ├── .env.example
  ├── src/
  │   ├── acquire/                # Stage 1 downloaders
  │   ├── parse/                  # Stage 2 parsers
  │   ├── resolve/                # Stage 3 NER + disambiguation
  │   ├── graph/                  # Stage 4 Neo4j loaders
  │   ├── enrich/                 # Stage 5 metrics + classification
  │   ├── models/                 # Pydantic models for all node/edge types
  │   └── utils/                  # Arabic text processing helpers
  ├── data/
  │   ├── raw/                    # gitignored, populated by acquire
  │   ├── staging/                # parquet intermediates
  │   └── curated/                # manual data (historical_events.yaml, etc.)
  ├── notebooks/                  # exploratory analysis
  ├── tests/
  └── queries/                    # saved Cypher queries
  ```
- Docker compose: Neo4j 5.x, PostgreSQL 16 + pgvector, Redis (optional cache)
- Pydantic models for all node and edge types (strict validation)
- Makefile targets: `make acquire`, `make parse`, `make resolve`, `make load`, `make enrich`

**Claude Code instructions:**
```
Initialize a Python monorepo called isnad-graph. Use uv for dependency management.
Create the directory structure above. Write Pydantic v2 models in src/models/ for
NARRATOR, HADITH, COLLECTION, CHAIN, GRADING, HISTORICAL_EVENT, LOCATION
matching the schema in this PRD. Include enum types for all enum fields.
Write a docker-compose.yml with Neo4j 5.x (APOC plugin enabled), PostgreSQL 16
with pgvector extension, and a shared network. Add a Makefile with stub targets.
```

---

### Phase 1: Data Acquisition & Parsing (Weeks 2–3)

**Objective:** Download all sources, parse into normalized Parquet staging tables.

**Tasks:**
1. **Downloaders** (`src/acquire/`)
   - `lk.py` — Clone LK corpus, handle CSV encoding (NOT Excel-compatible).
   - `sanadset.py` — Kaggle API download, extract CSVs.
   - `narrators.py` — Kaggle narrators dataset + scrape thehadith.co.uk.
   - `thaqalayn.py` — Fetch from ThaqalaynAPI `/api/v2/allbooks` + paginated hadith fetch.
   - `fawaz.py` — Download editions.json, then bulk-fetch all edition JSONs from CDN.
   - `sunnah.py` — API key auth, paginated fetch of all collections.
   - `muhaddithat.py` — Clone isnad-datasets repo.

2. **Parsers** (`src/parse/`)
   - One parser per source, outputting Parquet files conforming to staging schemas.
   - Arabic text utilities: diacritics stripping (for search), normalization (alif/hamza variants), encoding validation.
   - LK parser must handle the 16-column schema with correct column mapping.
   - Sanadset parser must extract `<NAR>` tagged entities into structured narrator lists.

**Exit criteria:** All sources downloaded. Parquet files in `data/staging/`. Row counts match expected totals. Unit tests for each parser.

**Claude Code instructions:**
```
In src/acquire/, write downloaders for each data source listed in the PRD.
Use httpx for API calls, kaggle CLI for Kaggle datasets, git for GitHub repos.
In src/parse/, write parsers that read raw files and output Parquet via pyarrow.
Create a shared Arabic text utility module in src/utils/arabic.py with functions:
strip_diacritics(), normalize_alif(), normalize_hamza(), clean_whitespace().
Write pytest tests in tests/test_parse/ that validate column schemas and row counts
against known values (e.g., LK Bukhari should have ~7,563 rows).
```

---

### Phase 2: Entity Resolution (Weeks 4–6)

**Objective:** Extract narrator entities from isnad text, disambiguate across corpora, deduplicate hadiths.

**Tasks:**
1. **Narrator NER** (`src/resolve/ner.py`)
   - For Sanadset: already tagged with `<NAR>`, extract directly.
   - For LK corpus: build rule-based extractor using Arabic transmission phrases:
     - `حدثنا` (haddathana), `أخبرنا` (akhbarana), `عن` (an), `سمعت` (sami'tu), `قال` (qala)
   - Fallback: CAMeLBERT-based NER for complex cases.
   - Output: list of (hadith_id, position, narrator_mention_text) tuples.

2. **Narrator Disambiguation** (`src/resolve/disambiguate.py`)
   - Build candidate narrator table from all sources (bio dataset, Sanadset narrators, LK mentions, muhaddithat IDs).
   - Disambiguation pipeline:
     1. Exact match on full name (Arabic, normalized).
     2. Fuzzy match (Levenshtein distance ≤ 2 on normalized Arabic).
     3. Temporal constraint: narrator lifetimes must overlap in the chain.
     4. Geographic constraint: narrator locations must be plausibly connected.
     5. Cross-reference: muslimscholars.info IDs where available.
   - Output: `narrators_canonical.parquet` with canonical IDs and merged metadata.
   - **Human-in-the-loop:** Generate an `ambiguous_narrators.csv` for manual review. Include top-3 candidate matches with confidence scores.

3. **Hadith Deduplication** (`src/resolve/dedup.py`)
   - Generate sentence-transformer embeddings for all matn_en texts.
   - Compute pairwise cosine similarity (use FAISS for efficiency at scale).
   - Threshold: ≥ 0.90 = likely duplicate (same hadith, same or different collection).
   - Threshold: 0.80–0.89 = parallel variant (similar teaching, different wording).
   - Threshold: 0.70–0.79 = thematic parallel (related topic, different hadith).
   - Cross-sect pairs (Sunni source ↔ Shia source) flagged separately.
   - Output: `parallel_links.parquet` with (hadith_id_a, hadith_id_b, similarity_score, variant_type, cross_sect).

**Exit criteria:** ≥85% narrator mentions resolved to canonical IDs. Ambiguous cases exported for review. Parallel links generated with similarity scores. All intermediate outputs in Parquet.

**Claude Code instructions:**
```
Build the NER pipeline in src/resolve/ner.py. Start with rule-based extraction
using Arabic transmission phrase patterns. Parse isnad strings left-to-right,
splitting on known phrases to extract narrator name spans.
Build disambiguation in src/resolve/disambiguate.py using rapidfuzz for fuzzy
matching on Arabic-normalized names. Use temporal overlap as a hard constraint.
Build dedup in src/resolve/dedup.py using sentence-transformers and FAISS.
Use the model 'paraphrase-multilingual-MiniLM-L12-v2' for embeddings.
Write integration tests that verify a known chain (e.g., Bukhari #1: Umar → Alqama
→ Ibrahim → ...) is correctly decomposed and all narrators resolved.
```

---

### Phase 3: Graph Construction (Weeks 7–8)

**Objective:** Load all resolved data into Neo4j. Establish all relationships.

**Tasks:**
1. **Node loading** (`src/graph/load_nodes.py`)
   - Batch-insert NARRATOR, HADITH, COLLECTION, GRADING nodes via Neo4j Python driver.
   - Use `UNWIND` + `MERGE` for idempotent loading.
   - Set unique constraints on all node IDs.

2. **Edge loading** (`src/graph/load_edges.py`)
   - TRANSMITTED_TO: For each chain, create edges between consecutive narrators.
   - APPEARS_IN: Link hadiths to collections with book/chapter/hadith numbers.
   - PARALLEL_OF: Load from parallel_links.parquet.
   - STUDIED_UNDER: Infer from biographical data where teacher-student relationships are documented.
   - GRADED_BY: Link hadiths to grading records.

3. **Validation queries** (`queries/validation/`)
   - Orphan check: narrators with no edges.
   - Chain integrity: every TRANSMITTED_TO path should form a valid DAG from originator to compiler.
   - Collection coverage: verify expected hadith counts per collection.

**Exit criteria:** Graph loaded. Validation queries pass. Neo4j Browser accessible for exploratory querying.

**Claude Code instructions:**
```
Write Neo4j loaders in src/graph/ using the neo4j Python driver. Use batch
UNWIND operations for performance (batch size 1000). Create unique constraints
on :Narrator(id), :Hadith(id), :Collection(id) before loading.
For chain edge construction: iterate resolved chains, create (n1)-[:TRANSMITTED_TO]->(n2)
for each consecutive narrator pair. Set position_in_chain as edge property.
Write Cypher validation queries in queries/validation/ that check for orphan nodes,
broken chains, and collection coverage. Run these as pytest fixtures.
```

---

### Phase 4: Enrichment & Analytics (Weeks 9–12)

**Objective:** Compute graph metrics, topic classification, historical overlay. Build analytical queries.

**Tasks:**
1. **Graph metrics** (`src/enrich/metrics.py`)
   - Betweenness centrality on TRANSMITTED_TO graph → identifies madār narrators.
   - In-degree / out-degree per narrator → transmission volume.
   - PageRank → narrator influence weighting.
   - Community detection (Louvain) → transmission school clusters.
   - Store all metrics as NARRATOR node properties.

2. **Topic classification** (`src/enrich/topics.py`)
   - Zero-shot classification on matn_en using `facebook/bart-large-mnli`.
   - Candidate labels: theology, jurisprudence, eschatology, succession/imamate, ritual/worship, ethics/conduct, history/sira, commerce/trade, warfare/jihad, family_law, food/drink, medicine, dreams/visions, end_times.
   - Store top-3 topics with confidence scores on HADITH nodes.

3. **Historical overlay** (`data/curated/historical_events.yaml`)
   - Manually curate a timeline: Rashidun caliphate, First Fitna, Umayyad period, Second Fitna, Abbasid revolution, Mihna, etc.
   - Link narrators to events via date overlap.
   - Create ACTIVE_DURING edges.

4. **Analytical query library** (`queries/analysis/`)
   - `bottleneck_narrators.cypher` — Top-N narrators by betweenness centrality.
   - `narrator_volume.cypher` — Hadith count per narrator, segmented by collection and grade.
   - `temporal_anomalies.cypher` — Chains where narrator death dates make transmission impossible.
   - `sectarian_parallels.cypher` — Hadiths appearing in both Sunni and Shia corpora.
   - `political_correlation.cypher` — Hadiths on succession/imamate topics, grouped by narrator's caliphate period.
   - `geographic_flow.cypher` — Hadith transmission paths mapped to locations over time.
   - `school_clusters.cypher` — Narrator communities from Louvain, annotated by geographic/temporal attributes.

**Exit criteria:** All metrics computed and stored. Topic tags assigned. Historical overlay in place. Query library tested against known results (e.g., Abu Hurayra should rank high in degree centrality).

**Claude Code instructions:**
```
Use Neo4j GDS (Graph Data Science) library for centrality and community detection.
Write src/enrich/metrics.py to project a named graph from TRANSMITTED_TO edges,
run betweenness centrality, PageRank, and Louvain community detection, then write
results back to NARRATOR node properties. Use GDS Cypher procedures.
Write src/enrich/topics.py using transformers pipeline('zero-shot-classification')
with facebook/bart-large-mnli. Process hadiths in batches of 32.
Create queries/analysis/ directory with the Cypher queries listed in the PRD.
Each query should be a standalone .cypher file with header comments explaining purpose.
```

---

### Phase 5: Visualization & Interface (Weeks 13–16)

**Objective:** Build a web-based exploration interface.

**Tasks:**
1. **API layer** — FastAPI service exposing graph queries as REST endpoints.
2. **Graph visualization** — Force-directed isnad graph using D3.js or vis.js.
3. **Narrator profile pages** — Biographical data + transmission stats + chain visualizations.
4. **Hadith detail view** — Matn text + isnad chain visualization + parallel hadiths + gradings.
5. **Search** — Full-text (PostgreSQL `tsvector`) + semantic (pgvector cosine similarity).
6. **Timeline view** — Historical events overlaid with narrator activity periods and hadith circulation.
7. **Comparative view** — Side-by-side Sunni/Shia parallel hadiths with divergent chain highlighting.

**Technology:** React + TypeScript frontend. FastAPI backend. Neo4j driver for graph queries. PostgreSQL for text search and metadata.

---

## 5. Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Narrator disambiguation accuracy | **High** | Rule-based + fuzzy + temporal constraints. Human-in-the-loop for ambiguous cases. Iterative refinement. Budget 40% of Phase 2 time for this. |
| Arabic NER on classical text | **High** | Start rule-based (transmission phrases are highly formulaic). Fine-tune CAMeLBERT only if rule-based < 80% recall. |
| Shia data structural mismatch | **Medium** | Thaqalayn data has different schema than Sunni sources. Build dedicated parser with explicit field mapping. |
| Cross-sect matn similarity | **Medium** | Arabic embeddings may miss semantic parallels. Use multilingual model on English translations as primary, Arabic as confirmatory. |
| Neo4j performance at scale | **Medium** | 650K hadiths × avg 5 chain links = ~3.25M edges. Well within Neo4j Community limits. Index on narrator_id and hadith_id. |
| Historical event curation | **Low** | Manual effort required. Start with major events (30–50), expand iteratively. Source from Tabari, Ibn Khaldun timelines. |
| Data licensing | **Low** | All sources are open-source or public domain. Thaqalayn is educational/academic use. Sunnah.com API requires key but data is freely available. |

---

## 6. Success Metrics

- **Phase 1:** All 7 data sources acquired and parsed. ≥95% of rows successfully parsed.
- **Phase 2:** ≥85% narrator mentions resolved. ≥90% of known parallel hadiths (Bukhari-Muslim overlap) detected by dedup.
- **Phase 3:** Graph loaded. All validation queries pass. Zero orphan narrator nodes.
- **Phase 4:** Betweenness centrality top-10 matches known common-link narrators from academic literature (al-Zuhri, Nafi', etc.). Topic classification F1 ≥ 0.75 on manually labeled sample.
- **Phase 5:** Sub-second query response for single-narrator lookups. Graph visualization renders chains up to 10 links without performance degradation.

---

## 7. Dependencies & Prerequisites

- Python 3.11+
- Neo4j 5.x with APOC and GDS plugins
- PostgreSQL 16+ with pgvector
- CUDA-capable GPU recommended for embedding generation (Phase 2, 4) but not required
- Kaggle API credentials for dataset downloads
- Sunnah.com API key (request via GitHub issue)
- ~50GB disk for raw data + staging + graph storage

---

## 8. Open Questions

1. **Narrator ID standard:** Should we mint our own canonical IDs or adopt muslimscholars.info numbering as the primary key system?
2. **Historical events granularity:** How deep should the political timeline go? Major caliphal transitions only, or provincial-level events (e.g., Zanj Rebellion, Qaramita raids)?
3. **Shia grading system:** Shia rijal methodology differs fundamentally from Sunni (four-tier vs. six-tier). Should gradings be normalized to a common scale or kept in their native systems?
4. **Scope of "parallel":** Is thematic similarity sufficient, or should parallel detection require structural isnad overlap as well?
5. **Language priority:** Should the primary analytical surface be Arabic or English translations? The LK corpus offers both, but semantic models perform differently on each.
