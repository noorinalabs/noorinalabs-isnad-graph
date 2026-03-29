# Operations URL Guide

> Single reference for all admin, monitoring, and operational endpoints on the
> isnad-graph platform. Intended for on-call engineers and operators.

**Production domain:** `isnad-graph.noorinalabs.com` (HTTPS via Caddy auto-TLS)

---

## Service URL Map

### Public Endpoints (no auth)

| URL | Method | Purpose | Notes |
|-----|--------|---------|-------|
| `https://isnad-graph.noorinalabs.com/` | GET | Frontend SPA | Served by Caddy -> nginx (frontend container) |
| `https://isnad-graph.noorinalabs.com/health` | GET | Comprehensive health check (per-service status) | Returns 200 if all healthy, 503 if degraded |
| `https://isnad-graph.noorinalabs.com/status` | GET | Public status summary | Lightweight operational status |
| `https://isnad-graph.noorinalabs.com/api/v1/auth/login/{provider}` | POST | OAuth login (Google, Apple, Facebook, GitHub) | Initiates OAuth flow |
| `https://isnad-graph.noorinalabs.com/api/v1/auth/callback/{provider}` | GET | OAuth callback | Handles provider redirect |
| `https://isnad-graph.noorinalabs.com/docs` | GET | Swagger UI (OpenAPI) | Interactive API documentation |
| `https://isnad-graph.noorinalabs.com/redoc` | GET | ReDoc (OpenAPI) | Alternative API documentation |
| `https://isnad-graph.noorinalabs.com/openapi.json` | GET | OpenAPI JSON schema | Machine-readable spec |

### Authenticated API Endpoints (require valid JWT)

| URL pattern | Purpose |
|-------------|---------|
| `/api/v1/narrators/...` | Narrator CRUD and search |
| `/api/v1/hadiths/...` | Hadith CRUD and search |
| `/api/v1/collections/...` | Collection browsing |
| `/api/v1/graph/...` | Graph traversal and visualization |
| `/api/v1/search/...` | Full-text and semantic search |
| `/api/v1/parallels/...` | Cross-collection parallel detection |
| `/api/v1/timeline/...` | Historical timeline queries |
| `/api/v1/auth/me` | Current user profile |
| `/api/v1/auth/refresh` | Token refresh |
| `/api/v1/auth/logout` | Session logout |
| `/api/v1/auth/2fa/enroll` | 2FA enrollment |
| `/api/v1/auth/2fa/verify` | 2FA verification |
| `/api/v1/auth/2fa/recovery` | 2FA recovery |

### Admin Endpoints (require admin role)

| URL | Method | Purpose |
|-----|--------|---------|
| `/api/v1/admin/users` | GET | List all users (paginated) |
| `/api/v1/admin/users/{user_id}` | GET | Get user details |
| `/api/v1/admin/users/{user_id}` | PATCH | Update user (role, status) |
| `/api/v1/admin/health/live` | GET | Liveness probe |
| `/api/v1/admin/health/ready` | GET | Readiness probe (checks Neo4j, PostgreSQL, Redis) |
| `/api/v1/admin/stats` | GET | Content statistics |
| `/api/v1/admin/analytics` | GET | Usage analytics |
| `/api/v1/admin/moderation` | GET | Moderation queue (paginated) |
| `/api/v1/admin/moderation/{item_id}` | PATCH | Update moderation item |
| `/api/v1/admin/moderation/flag` | POST | Flag content for moderation |
| `/api/v1/admin/reports` | GET | System reports |
| `/api/v1/admin/config` | GET | System configuration |
| `/api/v1/admin/config` | PATCH | Update system configuration |
| `/api/v1/admin/config/audit` | GET | Configuration audit log |

### Observability (infrastructure-only)

These services are exposed on the host but **not** proxied through Caddy. Access
requires direct network access to the server (VPN or SSH tunnel).

| URL | Service | Port | Purpose |
|-----|---------|------|---------|
| `http://<host>:9090` | Prometheus | 9090 | Metrics UI, PromQL queries |
| `http://<host>:9093` | AlertManager | 9093 | Alert management UI |
| `https://isnad-graph.noorinalabs.com/grafana` | Grafana | 3000 (internal) | Dashboards and log exploration (proxied via Caddy) |
| `http://<host>:3100` | Loki | 3100 | Log aggregation API |
| `http://<host>:9100/metrics` | Node Exporter | 9100 | Host-level metrics (CPU, memory, disk) |
| `http://<host>:9187/metrics` | Postgres Exporter | 9187 | PostgreSQL metrics |
| `http://<host>:7474` | Neo4j Browser | 7474 | Graph database UI (HTTP) |
| `bolt://<host>:7687` | Neo4j Bolt | 7687 | Graph database wire protocol |

**Grafana authentication:** Login required. Default admin credentials set via
`GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` environment variables.

### Prometheus Metrics Endpoint

| URL | Purpose |
|-----|---------|
| `/metrics` | FastAPI application metrics (exposed by `prometheus-fastapi-instrumentator`, not in OpenAPI schema) |

---

## Docker Compose Service-to-Port Mapping

### Production (`docker-compose.prod.yml`)

| Service | Internal Port | Exposed Port | Network | Notes |
|---------|---------------|--------------|---------|-------|
| `caddy` | 80, 443 | 80, 443 | backend, frontend | Reverse proxy, auto-TLS |
| `api` | 8000 | not exposed | backend, frontend | Proxied via Caddy at `/api/*` |
| `frontend` | 80 | not exposed | frontend | Proxied via Caddy (default route) |
| `neo4j` | 7474, 7687 | 7474, 7687 | backend | HTTP browser + Bolt protocol |
| `postgres` | 5432 | 127.0.0.1:5432 | backend | Localhost-only |
| `redis` | 6379 | 127.0.0.1:6379 | backend | Localhost-only, password required |
| `prometheus` | 9090 | 9090 | backend | Metrics + alerting rules |
| `alertmanager` | 9093 | 9093 | backend | Alert routing |
| `grafana` | 3000 | not exposed | backend | Proxied via Caddy at `/grafana/*` |
| `loki` | 3100 | 3100 | backend | Log aggregation |
| `promtail` | 9080 | not exposed | backend | Log shipper (reads Docker logs) |
| `node-exporter` | 9100 | 9100 | backend | Host metrics |
| `postgres-exporter` | 9187 | 9187 | backend | PostgreSQL metrics |

### Development (`docker-compose.yml`)

| Service | Exposed Port | Notes |
|---------|--------------|-------|
| `neo4j` | 7474, 7687 | Default creds: `neo4j/isnad_graph_dev` |
| `postgres` | 5432 | Default creds: `isnad/isnad_dev`, DB: `isnad_graph` |
| `redis` | 6379 | No password |
| `api` | 8000 | Direct access, no reverse proxy |
| `frontend` | 3000 | Direct access via nginx |

---

## Network Segmentation (Production)

```
Internet
  │
  ▼
┌──────────┐
│  Caddy   │ ports 80/443
│ (TLS)    │
└─┬──────┬─┘
  │      │
  │   ┌──┴──────────┐  frontend network
  │   │   frontend   │
  │   └──────────────┘
  │
  ├──→ api ──→ neo4j, postgres, redis     backend network (internal)
  │
  └──→ grafana                             backend network (internal)

Prometheus, AlertManager, Loki, exporters  backend network (internal)
```

The `backend` network is **internal** (no direct internet access). Only `caddy`
and `api` bridge both networks.

---

## Troubleshooting

### API is not responding

1. Check the API container: `docker compose -f docker-compose.prod.yml logs api --tail 50`
2. Verify health: `curl -sf http://localhost:8000/health` (from the host)
3. Check dependencies — the API depends on Neo4j, PostgreSQL, and Redis all being healthy
4. Verify Caddy is routing correctly: `docker compose -f docker-compose.prod.yml logs caddy --tail 20`

### Health check returns "degraded"

1. Hit `/health` to see which service is down (response includes per-service status with latency)
2. Check the failing service logs: `docker compose -f docker-compose.prod.yml logs <service> --tail 50`
3. Verify the service container is running: `docker compose -f docker-compose.prod.yml ps`
4. For Neo4j: check heap/pagecache memory — OOM kills are common with large datasets
5. For PostgreSQL: check `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB` from inside the container
6. For Redis: verify password matches `REDIS_PASSWORD` env var

### Grafana is unreachable

1. Grafana is proxied through Caddy at `/grafana/` — confirm Caddy is running
2. Check Grafana health: `docker compose -f docker-compose.prod.yml exec grafana wget -qO- http://localhost:3000/api/health`
3. Grafana depends on Prometheus and Loki — check those services first
4. Verify `GF_SERVER_ROOT_URL` and `GF_SERVER_SERVE_FROM_SUB_PATH` are set correctly

### Prometheus is not scraping metrics

1. Check Prometheus targets: visit `http://<host>:9090/targets`
2. Verify the API `/metrics` endpoint is responding: `curl -sf http://localhost:8000/metrics | head`
3. Review scrape config: `infra/prometheus/prometheus.yml`
4. Check alert rules: `infra/prometheus/alerts.yml`

### AlertManager is not firing alerts

1. Check AlertManager UI: `http://<host>:9093`
2. Verify Prometheus alert rules are loaded: `http://<host>:9090/alerts`
3. Review AlertManager config: `infra/alertmanager/alertmanager.yml`
4. Check AlertManager logs: `docker compose -f docker-compose.prod.yml logs alertmanager --tail 20`

### Neo4j Browser is not loading

1. Neo4j Browser runs on port 7474 — verify it is exposed and not firewalled
2. Check container status: `docker compose -f docker-compose.prod.yml ps neo4j`
3. Test Bolt connectivity: `cypher-shell -u neo4j -p $NEO4J_PASSWORD "RETURN 1"`
4. Check Neo4j logs for memory issues: `docker compose -f docker-compose.prod.yml logs neo4j --tail 50`

### Logs are not appearing in Grafana/Loki

1. Check Loki health: `curl -sf http://localhost:3100/ready`
2. Check Promtail is running and scraping: `docker compose -f docker-compose.prod.yml logs promtail --tail 20`
3. Verify Promtail has access to Docker socket (`/var/run/docker.sock`)
4. Confirm Grafana has Loki configured as a data source in `infra/grafana/provisioning/`
