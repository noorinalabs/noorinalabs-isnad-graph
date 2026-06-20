---
name: feedback_shared_redis_ratelimit_test_429
description: isnad-graph local API tests intermittently 429 under parallel agents — shared Redis rate-limit bucket keyed by constant testclient IP; isolate via REDIS_URL db
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b923c0f4-c87a-4bed-b4b8-91a79287509b
---

isnad-graph backend API tests (FastAPI `client.get` via TestClient) can fail intermittently with **429 Too Many Requests** when several agents run api-test suites concurrently on the same box. Not a code bug — an environmental artifact.

Cause: a Redis server is live on `localhost:6379` and the app's `RateLimitMiddleware` (default 60 req/min, `src/api/middleware.py`) keys its sliding window on the client IP. TestClient's IP is the constant string `testclient`, so EVERY test process across EVERY worktree shares the one Redis sorted set `ratelimit:testclient` in DB 0. Under concurrent sibling load the shared bucket exceeds 60/window and unrelated tests 429. The `app`/`client` fixtures are function-scoped (fresh in-memory limiter per test), so with NO Redis it never accumulates — which is why **CI is green** (isolated per-job) even though local runs flake.

Tells it's this and not your change: every failure is a `429`, never an assertion; the same test passes in isolation; full file passes on an isolated bucket.

**How to apply:** run local api tests against an isolated Redis DB so the bucket is private:
`ENVIRONMENT=test REDIS_URL="redis://localhost:6379/15" uv run pytest ...`
(also works for the pre-push hook: prefix the `git push` with the same env so the hook's pytest inherits it). `redis-cli` is NOT installed on the box; probe the listener with `ss -ltnp | grep 6379`. Found during ig#1060 (P5W4). Durable test-isolation fix (reset/namespace the limiter bucket per test, or skip rate-limit middleware in tests) would belong in a follow-up issue, not a feature PR. Related: [[feedback_no_head_in_surface_enumeration]] is unrelated; see rate-limit middleware.
