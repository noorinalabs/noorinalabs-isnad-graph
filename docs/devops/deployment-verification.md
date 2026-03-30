# Deployment Verification Process

This document describes the production deployment verification process for isnad-graph, hosted at `https://isnad-graph.noorinalabs.com` on a Hetzner VPS.

## Overview

After every deployment to production (triggered by push to `main`), we run a suite of automated checks to verify the deployment is healthy. This runs in two modes:

1. **Automated** — the `verify-deploy.yml` GitHub Actions workflow triggers after each deploy
2. **Manual** — the `scripts/verify_deployment.sh` script can be run from any machine

## What Gets Checked

| Check | Description | Pass Criteria |
|-------|-------------|---------------|
| Deploy workflow | Latest `deploy.yml` run status | `conclusion=success` |
| Live site | HTTP response from site root | HTTP 200 |
| Health endpoint | `/health` returns valid JSON | `status=healthy` |
| Status endpoint | `/status` per-service health | Neo4j, PostgreSQL, Redis all healthy |
| API endpoints | Smoke test protected routes | HTTP 401/403 (auth required) or 200 |
| Security headers | Required HTTP headers present | All 6 headers set |
| SSL certificate | Certificate validity | >14 days until expiry |
| Response time | Health endpoint latency | p95 < 500ms |

### Required Security Headers

- `X-Content-Type-Options` (expected: `nosniff`)
- `X-Frame-Options` (expected: `DENY` or `SAMEORIGIN`)
- `Strict-Transport-Security` (expected: HSTS with `max-age`)
- `X-XSS-Protection` (expected: `1; mode=block`)
- `Referrer-Policy`
- `Content-Security-Policy`

## Manual Verification

```bash
# Full check against production
./scripts/verify_deployment.sh

# Custom site URL
./scripts/verify_deployment.sh --site=https://staging.noorinalabs.com

# Skip workflow check (e.g., from a non-GitHub environment)
./scripts/verify_deployment.sh --skip-workflow

# Skip SSL check (e.g., local/HTTP-only target)
./scripts/verify_deployment.sh --skip-ssl
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SITE_URL` | `https://isnad-graph.noorinalabs.com` | Target site URL |
| `GH_REPO` | `parametrization/isnad-graph` | GitHub repository for workflow checks |
| `ROLLBACK_TAG` | (empty) | If set, records current SHA for rollback reference |

## Automated Verification (CI)

The `verify-deploy.yml` workflow runs automatically after the `Deploy` workflow completes on `main`. It:

1. Waits 30 seconds for services to stabilize
2. Runs the verification script
3. Posts results as a job summary
4. Fails the workflow if any critical check fails

### Triggering Manually

```bash
gh workflow run verify-deploy.yml
```

## Rollback Procedure

If verification fails:

1. Check the deploy workflow logs: `gh run view --log`
2. SSH to the VPS to inspect container logs:
   ```bash
   ssh deploy@<VPS_HOST> 'docker compose -f /opt/isnad-graph/docker-compose.prod.yml logs --tail=100'
   ```
3. If the issue is in new code, revert the merge to `main` and push — the deploy workflow will redeploy the previous state
4. If infrastructure is broken, SSH in and restart services:
   ```bash
   ssh deploy@<VPS_HOST> 'cd /opt/isnad-graph && docker compose -f docker-compose.prod.yml restart'
   ```

## Neo4j Data Verification

The health and status endpoints validate that Neo4j is reachable. For deeper data verification, the API's graph endpoints (`/api/v1/graph`, `/api/v1/narrators`) require authentication. The smoke tests verify these endpoints return HTTP 401/403 (confirming the API layer and auth middleware are operational) rather than connection errors.

To verify Neo4j data content after deployment, use an authenticated request:

```bash
# After obtaining a JWT token via the auth flow:
curl -H "Authorization: Bearer $TOKEN" https://isnad-graph.noorinalabs.com/api/v1/narrators?limit=5
```

## Blue-Green Deployment Considerations

The current deployment strategy is rolling (in-place update via `docker compose up -d`). For zero-downtime deployments, a blue-green approach would require:

- Two sets of services behind a reverse proxy (e.g., nginx or Traefik)
- Health-check-based traffic switching
- The verification script could target the "green" environment before switching traffic

This is documented for future consideration but not yet implemented, as the current single-VPS setup has acceptable downtime windows for the project's scale.
