---
name: project_ig_integration_test_harness_gaps
description: ig make test-integration not e2e-green even after neo4j fixture auth fix; two pre-existing harness gaps unmasked
metadata: 
  node_type: memory
  type: project
  originSessionId: d8acc7c0-91ac-412b-b312-da38817b1614
---

ig#975 (PR#1102, L.Pham) fixed the `neo4j_client` integration fixture AuthError: testcontainers 4.x `Neo4jContainer._configure()` runs `with_env("NEO4J_AUTH", f"neo4j/{self.password}")` at start, clobbering the fixture's manual `with_env` (password defaulted to `password`). Fix = pass `Neo4jContainer("neo4j:5-community", password=NEO4J_TEST_PASSWORD)`.

That fix UNMASKED two pre-existing defects that previously hid behind the setup-time AuthError, so `make test-integration` is still not end-to-end green:
1. **API-auth 401** — `tests/integration/test_api_endpoints.py` `api_client` fixture builds the app + sets `app.state.neo4j` but injects NO bearer token / `app.dependency_overrides[require_auth]`, so every `require_auth` route (registered in `src/api/app.py`) returns 401. Harness gap; needs a follow-up issue.
2. **RateLimitMiddleware Redis `ping()` blocks ~133s/request** — this is [[feedback_api_pytest_redis_ping]], tracked by ig#1034 (add `socket_connect_timeout`).

Integration tests are NOT a CI gate (CI runs `pytest -m "not integration and not e2e"`), so these don't block PR checks. **How to apply:** when asked to "make test-integration pass", the neo4j fixture auth is only step 1 — the 401 auth-override + ig#1034 redis timeout must also land.
