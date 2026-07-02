# Project memory — noorinalabs-isnad-graph

In-repo, version-controlled memory for this repo (org/repo memory split — meta noorinalabs-main#740, driver #732). This `MEMORY.md` is the always-loaded index (one line per memory); the individual `*.md` files are read on demand when a line looks relevant. Some `[[wikilinks]]` point at org-level memories that remain in `noorinalabs-main/.claude/memory/` — those are acceptable soft cross-repo pointers.

- [API pytest hangs on Redis ping offline](feedback_api_pytest_redis_ping.md) — ig test_api/* times out: RateLimitMiddleware.redis.ping() blocks; stub _get_redis→None.
- [Shared Redis ratelimit → test 429s](feedback_shared_redis_ratelimit_test_429.md) — ig api tests flake 429 under parallel agents (shared ratelimit:testclient bucket). ig#1060.
- [Prod frontend runtime-config lag](feedback_prod_frontend_runtime_config_lag.md) — frontend resolves us origin via window.RUNTIME_CONFIG from /runtime-config.js; stale image lags. deploy#420.
- [FastAPI Depends(get_settings) → 422](project_ig_fastapi_depends_get_settings_422.md) — bare Depends(get_settings) 422s under MagicMock-patched suites. ig#1070/PR#1084.
- [ig integration test harness gaps](project_ig_integration_test_harness_gaps.md) — neo4j auth fixed (PR#1102); not e2e-green: 401 auth-override + ig#1034 redis ping.
- [Semantic search = hashing embedder](project_semantic_search_hashing_embedder.md) — query-embed correct; arbitrary results = corpus embedded w/ HashingEmbedder. ig#1071.
- [i18n scope](project_i18n_scope.md) — i18n is UI/navigation toggle only; source API data stays untransformed.
- [Semantic search prod gap + embedder parity](project_semantic_embedder_parity_prod.md) — ig#1148: app+job complete; prod unprovisioned (deploy#470) + torch-free API HashingEmbedder vs MiniLM corpus (200-with-garbage). Smoke=scripts/semantic_smoke.py.
