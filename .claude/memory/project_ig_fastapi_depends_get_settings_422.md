---
name: project_ig_fastapi_depends_get_settings_422
description: isnad-graph — bare Depends(get_settings) on a route 422s under suites that patch get_settings with a MagicMock; use a clean-signature wrapper dep
metadata: 
  node_type: memory
  type: project
  originSessionId: b923c0f4-c87a-4bed-b4b8-91a79287509b
---

isnad-graph FastAPI gotcha (ig#1070/PR#1084): adding a **bare `settings: Settings = Depends(get_settings)`** to a route silently regresses EVERY request on that route to **422** under the wider test suites.

**Why:** route modules are imported lazily *inside* `create_app()` (`from src.api.routes import search, ...`). test_auth/test_security conftests do `patch("src.config.get_settings", return_value=test_settings)` (a `MagicMock`). FastAPI then introspects the mock's `(*args, **kwargs)` signature and treats `args`/`kwargs` as **required query params** → `{"detail":[{"loc":["query","args"],"msg":"Field required"},...]}` 422. It's order/import-timing dependent, so it can pass in isolation and fail in the full suite.

**Fix pattern:** wrap it in a dedicated dependency with a clean `() -> Settings` signature:
```python
def get_search_settings() -> Settings:
    return get_settings()
# route: settings: Settings = Depends(get_search_settings)
```
FastAPI introspects the wrapper (clean sig, no params) — never the patched mock — while runtime still calls `get_settings()` (honouring patches). Tests override by the route module's own reference: `app.dependency_overrides[search_route.get_search_settings] = lambda: Settings(...)` — order-independent (don't key on `src.config.get_settings`, which suites monkeypatch).

Related: per-test rate-limit isolation — CI's unit `test` job has no shared Redis, so the rate-limit middleware falls back to in-memory **per-app** (fresh each test). This sandbox can't replicate by leaving Redis down (a down Redis **hangs** on connect — IPv6 `::1`, no socket timeout — instead of failing fast). To run the EXACT CI command locally green: `docker compose up -d neo4j postgres redis` + a throwaway pytest `-p` plugin that flushes Redis in `pytest_runtest_setup`. CI uses `-x` (stop at first failure). See [[feedback_runtime_gate_scoping]].
