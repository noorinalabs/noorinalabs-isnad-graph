---
name: feedback_api_pytest_redis_ping
description: isnad-graph API pytest appears to hang offline because RateLimitMiddleware.redis.ping() blocks per-request; neutralize the ping to run locally
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b923c0f4-c87a-4bed-b4b8-91a79287509b
---

isnad-graph `tests/test_api/*` (any route test using the `client`/`app` fixtures) **appears to hang** in this network-less sandbox — it crawls ~1 test per minute and times out before finishing. Not contention (load was 0.2, 25GB free) and NOT your code: `create_app()` is fast (~0.9s).

**Root cause:** `RateLimitMiddleware._get_redis()` (`src/api/middleware.py`) runs on the FIRST request of every test and does `redis.Redis.from_url(url).ping()`. With no Redis reachable, `ping()` blocks on a TCP connect timeout (no `socket_connect_timeout` set) before the `except` falls back to the in-memory limiter. The function is memoized per middleware instance, but the `app` fixture is function-scoped → new middleware → new blocking ping every test.

**Why:** an unset connect timeout turns "Redis absent" into a multi-minute per-request stall instead of an instant ECONNREFUSED.

**How to apply:** to run API tests locally, neutralize the ping with a throwaway (NOT committed) pytest plugin:
```python
# /tmp/redisstub.py
def pytest_configure(config):
    from src.api.middleware import RateLimitMiddleware
    RateLimitMiddleware._get_redis = lambda self: None
```
`ENVIRONMENT=test PYTHONPATH=/tmp .venv/bin/python -m pytest tests/test_api/test_parallels.py -p redisstub -o addopts="" -q` → full suite in ~1.5s. (Setting `REDIS_URL=redis://127.0.0.1:1/0` did NOT help — config reads a nested `redis.effective_url`, not that env var.) CI has Redis so it never sees this. Route test path prefix is `/api/v1` (`tests/test_api/routes.py` PREFIX). Verified P5W4 ig#1037/PR#1079. Possible durable fix: pass a short `socket_connect_timeout` in `_get_redis`. Related: [[feedback_runtime_gate_scoping]], [[feedback_wsl2_no_local_docker]].
