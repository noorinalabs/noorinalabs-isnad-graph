---
name: project_semantic_embedder_parity_prod
description: "Semantic search on prod (ig#1148): the app code + embed job are complete; the gap is prod provisioning (deploy#470) PLUS a latent embedder-parity mismatch — the torch-free API queries with HashingEmbedder while the re-embed job embeds the corpus with a MiniLM sentence-transformer (both vector(384), so 200-with-garbage, not an error). Smoke = scripts/semantic_smoke.py."
metadata:
  node_type: memory
  type: project
---

**ig#1148 — semantic search still fails on prod despite ig#1110.** Root cause is NOT app code:

- `search_semantic` (`src/api/routes/search.py:440-538`) already: embeds the query at request time, cosine-ranks `isnad_graph.hadith_embeddings`, returns a typed **graceful 503** ("not yet available on this environment") when the pgvector table/extension is absent OR the embedder can't be built, and returns **200** once the table is populated. Well-tested (55 semantic tests in `tests/test_api/test_search.py`).
- The embed job is complete: `run_embedding_load` / `ensure_embedding_schema` (`src/enrich/embeddings.py`) `CREATE EXTENSION IF NOT EXISTS vector` + backfill; CLI `isnad embed-hadiths | reindex-embeddings | verify-recall` (`src/cli.py`). Provisioning runs via deploy repo `reembed-corpus.yml` (`--profile embed`), which already supports `env=prod`.

**Two real gaps, both outside ig repo code:**

1. **Prod never provisioned/backfilled (deploy#470).** Per [[project_semantic_search_hashing_embedder]]: prod was never data-loaded (prod Neo4j had 0 nodes) and the prod compose predated the `isnad-graph-embed` service, so the prod re-embed 1s-failed at `compose pull`. Fixing prod = full prod cutover (load corpus → deploy-prod compose roll → run `reembed-corpus.yml env=prod`). Owner/production-approval gated. Verified at the promotion window, NOT PR acceptance.

2. **Embedder-parity mismatch (latent, would make backfilled prod return 200-with-garbage).** The API service in `noorinalabs-deploy/compose/docker-compose.prod.yml` sets **no `EMBEDDING_MODEL`** on the `isnad-graph-api` service, and the API runs the **lean, torch-free** runtime image → it can only build the default lexical `HashingEmbedder` (`src/config.py:217` `embedding_model="hashing"`). The re-embed job bakes `EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2` (compose `:245`). Both are `vector(384)`, so a HashingEmbedder query vector cosine-compares against MiniLM corpus vectors with **no error** — HTTP 200 with meaningless ranking. For prod to return *relevant* results the API and corpus embedders must MATCH: either give the API a model-capable image + `EMBEDDING_MODEL=<same MiniLM>`, or embed the corpus with `hashing`. This is a **deploy-repo config decision** (flag, don't edit from ig) and likely also affects stg's "it works" (stg API is also hashing).

**ig#1148 deliverable (this branch, `N.Obi/1148-semantic-search-prod`):** `src/api/semantic_smoke.py` + thin `scripts/semantic_smoke.py` — the endpoint-level smoke the issue's acceptance #3 asks for. It hits live `GET /api/v1/search/semantic`, requires 200 + non-empty + positive top score + a **topical keyword** in the top hits (reuses `verify_recall`'s `_RECALL_KEYWORDS`). The keyword assertion is what catches gap #2 (200-but-off-topic), which `isnad verify-recall` (DB-side, in the embed container with its own embedder) cannot. Tests: `tests/test_api/test_semantic_smoke.py`. Wire it into `noorinalabs-deploy` `verify_prod_smoke.sh` (currently only checks narrators auth) at the promotion window.
