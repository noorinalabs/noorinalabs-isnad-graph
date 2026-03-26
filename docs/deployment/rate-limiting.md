# Rate Limiting

The isnad-graph API enforces per-IP sliding-window rate limiting on all
endpoints. The implementation uses a Redis sorted set when available,
falling back to a per-process in-memory window for local development.

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `120` | Maximum requests allowed per client IP within the sliding window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Duration of the sliding window in seconds |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL used for shared rate-limit state |

These variables are loaded via `RateLimitSettings` and `RedisSettings` in
`src/config.py` (prefixed `RATE_LIMIT_` and `REDIS_` respectively).

## How it works

`RateLimitMiddleware` (in `src/api/middleware.py`) runs on every inbound
request:

1. Extracts the client IP from `X-Forwarded-For` or the connection scope.
2. Attempts a Redis-backed check using a sorted set keyed by
   `ratelimit:<ip>`. Timestamps outside the window are pruned, and the
   current count is compared against `RATE_LIMIT_REQUESTS_PER_MINUTE`.
3. If Redis is unreachable, falls back to an in-memory dictionary of
   timestamps per IP (per-process only).
4. Returns **429 Too Many Requests** with a `Retry-After` header when the
   limit is exceeded.

## Production: Redis is required

In production, multiple uvicorn workers serve the API behind a load
balancer. Without Redis, each worker tracks rate limits independently,
which means the effective limit is multiplied by the number of workers.

**Redis is a hard dependency for accurate rate limiting in production.**

The production Docker Compose (`docker-compose.prod.yml`) includes a Redis
service. Ensure `REDIS_URL` and `REDIS_PASSWORD` are set in your
production `.env`.

## Development: in-memory fallback

When Redis is not running (typical for local `uvicorn --reload`
development), the middleware automatically falls back to an in-memory
sliding window. This is adequate for single-process development but will
not share state across workers.

No special configuration is needed — if `REDIS_URL` is unreachable the
fallback activates silently.

## Tuning

- **Lowering `RATE_LIMIT_REQUESTS_PER_MINUTE`** protects expensive graph
  queries from abuse but may impact legitimate bulk consumers (e.g.,
  admin dashboards polling multiple endpoints).
- **Increasing `RATE_LIMIT_WINDOW_SECONDS`** smooths burst traffic but
  makes the limit harder for callers to reason about.
- For per-endpoint or per-user limits, extend `RateLimitMiddleware` with
  route-aware or token-aware bucketing.

## Monitoring

When Prometheus instrumentation is enabled, rate-limited responses appear
as `429` status codes in the `http_requests_total` counter. Set up a
Grafana alert on a spike in `429` responses to detect abuse or
misconfiguration.
