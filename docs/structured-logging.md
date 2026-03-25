# Structured Logging

The isnad-graph platform uses [structlog](https://www.structlog.org/) for structured logging across all backend services.

## Log Format

All log output follows a consistent schema. When `LOG_FORMAT=json` (recommended for production), each log line is a single JSON object:

```json
{
  "timestamp": "2026-03-25T12:34:56.789000Z",
  "level": "info",
  "service": "isnad-graph",
  "logger_name": "src.api.middleware",
  "event": "request_completed",
  "request_id": "a1b2c3d4e5f6...",
  "method": "GET",
  "path": "/api/v1/narrators",
  "status_code": 200,
  "duration_ms": 42.3
}
```

### Standard Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | ISO-8601 UTC timestamp |
| `level` | string | Log level: `debug`, `info`, `warning`, `error`, `critical` |
| `service` | string | Always `isnad-graph` |
| `logger_name` | string | Python module that emitted the log |
| `event` | string | Event name / human-readable message |

### API Request Fields

API requests include additional fields via the `RequestLoggingMiddleware`:

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Unique ID per request (UUID4 hex or client-supplied) |
| `method` | string | HTTP method (GET, POST, etc.) |
| `path` | string | Request path |
| `status_code` | int | HTTP response status (on `request_completed`) |
| `duration_ms` | float | Request duration in milliseconds |

## Configuration

Two environment variables control logging behavior:

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Minimum log level. Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_FORMAT` | `console` | Output format. `json` for structured JSON, `console` for human-readable |

Set these in `.env` or as environment variables:

```bash
LOG_LEVEL=DEBUG
LOG_FORMAT=json
```

## Request ID Tracing

Every API request is assigned a unique `request_id`:

- If the client sends an `X-Request-ID` header, it is used (truncated to 64 chars)
- Otherwise, a UUID4 hex string is generated
- The `request_id` is included in all log lines within the request scope
- The `X-Request-ID` header is returned in the response for client-side correlation

## Usage in Code

```python
from src.utils.logging import get_logger

log = get_logger(__name__)

log.info("operation_started", entity_id="nar:001")
log.warning("slow_query", duration_ms=1500, query="MATCH ...")
log.error("connection_failed", service="neo4j", retries=3)
```

## Architecture

Logging is configured centrally in `src/utils/logging.py`:

- `configure_logging()` — called once at module import time; reads `LOG_LEVEL` and `LOG_FORMAT`
- `get_logger(name)` — returns a structlog bound logger with `logger_name` set
- `_add_service_name` — processor that injects the `service` field
- `RequestLoggingMiddleware` — FastAPI middleware that assigns request IDs and logs request lifecycle

The middleware uses `structlog.contextvars` to bind `request_id`, `method`, and `path` to all log lines within a request without explicit passing.
