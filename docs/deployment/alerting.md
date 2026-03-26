# Alerting Setup

This document describes the Prometheus alerting rules and Alertmanager configuration for the isnad-graph production stack.

## Architecture

```
Prometheus (evaluates rules) → Alertmanager (routes/deduplicates) → Webhook / Email
```

- **Alert rules** are defined in `infra/prometheus/alerts.yml` and loaded by Prometheus.
- **Alertmanager** receives firing alerts from Prometheus, groups them, and routes to configured receivers.
- **Grafana** can query Prometheus alert state via the Prometheus datasource.

## Configuration Files

| File | Purpose |
|------|---------|
| `infra/prometheus/alerts.yml` | Prometheus alerting rules |
| `infra/prometheus/prometheus.yml` | Prometheus config (references alerts + Alertmanager) |
| `infra/alertmanager/alertmanager.yml` | Alertmanager routing and receiver config |

## Alert Rules

### ServiceDown

- **Severity:** critical
- **Condition:** Any Prometheus scrape target is unreachable for >1 minute.
- **Remediation:**
  1. Check `docker compose -f docker-compose.prod.yml ps` for stopped/unhealthy containers.
  2. Check container logs: `docker compose -f docker-compose.prod.yml logs <service>`.
  3. Restart the service: `docker compose -f docker-compose.prod.yml restart <service>`.
  4. If persistent, check resource limits and host disk/memory.

### ContainerUnhealthy

- **Severity:** critical
- **Condition:** A monitored container reports unhealthy for >1 minute (based on `up` metric over a 2-minute window).
- **Remediation:** Same as ServiceDown.

### HighErrorRate

- **Severity:** critical
- **Condition:** API 5xx error rate exceeds 5% over 5 minutes.
- **Remediation:**
  1. Check API logs in Grafana Explore (Loki datasource): `{service="api"} |= "ERROR"`.
  2. Look for patterns in error responses — database connectivity, OOM, or application bugs.
  3. Check dependent services (Neo4j, PostgreSQL, Redis) health.
  4. If caused by a recent deployment, consider rolling back.

### HighLatencyP95

- **Severity:** warning
- **Condition:** API p95 latency exceeds 2 seconds for 5 minutes.
- **Remediation:**
  1. Check Grafana API dashboard for slow endpoints.
  2. Check Neo4j and PostgreSQL query performance.
  3. Look for resource contention (CPU/memory) on the host.
  4. Consider scaling API workers or optimizing slow queries.

### HighDiskUsage

- **Severity:** warning
- **Condition:** Root filesystem usage exceeds 80% for 5 minutes.
- **Remediation:**
  1. Check Docker volume usage: `docker system df`.
  2. Prune unused images/containers: `docker system prune`.
  3. Check log rotation is working (JSON log driver limits).
  4. Review Loki and Prometheus data retention settings.
  5. Consider expanding disk if usage is legitimate.

### HighMemoryUsage

- **Severity:** warning
- **Condition:** System memory usage exceeds 85% for 5 minutes.
- **Remediation:**
  1. Check per-container memory: `docker stats`.
  2. Identify containers exceeding their reservations.
  3. Check for memory leaks in the API service.
  4. Consider reducing Neo4j heap/pagecache or API worker count.

### BackupFailure

- **Severity:** warning
- **Condition:** No successful backup recorded in the last 24 hours (requires `isnad_backup_last_success_timestamp_seconds` metric).
- **Remediation:**
  1. Check backup timer: `systemctl status isnad-backup.timer`.
  2. Check backup service logs: `journalctl -u isnad-backup.service`.
  3. Run backup manually: `scripts/backup.sh`.
  4. Verify backup destination has sufficient space.

## Notification Configuration

### Webhook (Default)

Alertmanager sends alert payloads to a webhook URL. Configure via the `ALERTMANAGER_WEBHOOK_URL` environment variable. The default placeholder is `http://localhost:9095/webhook`.

Common webhook integrations:
- **Slack:** Use a Slack incoming webhook URL.
- **PagerDuty:** Use PagerDuty Events API v2 endpoint.
- **Custom:** Any HTTP endpoint that accepts POST with JSON body.

### Email (Optional)

Uncomment the `email_configs` section in `infra/alertmanager/alertmanager.yml` and set the following environment variables:

| Variable | Description |
|----------|-------------|
| `ALERT_EMAIL_TO` | Recipient email address |
| `ALERT_EMAIL_FROM` | Sender email address |
| `ALERT_SMTP_HOST` | SMTP server hostname |
| `ALERT_SMTP_PORT` | SMTP server port (typically 587) |
| `ALERT_SMTP_USER` | SMTP authentication username |
| `ALERT_SMTP_PASSWORD` | SMTP authentication password |

## Routing

- **Critical alerts** (service down, high error rate) are sent to the `critical` receiver with a 1-hour repeat interval.
- **Warning alerts** (latency, disk, memory, backup) go to the `default` receiver with a 4-hour repeat interval.
- **Inhibition:** If a critical alert fires, matching warning alerts for the same instance are suppressed to reduce noise.

## Verifying Alerts

1. Check active alerts in Prometheus: `http://localhost:9090/alerts`
2. Check Alertmanager status: `http://localhost:9093/#/alerts`
3. Test with a synthetic alert:
   ```bash
   curl -X POST http://localhost:9093/api/v2/alerts \
     -H "Content-Type: application/json" \
     -d '[{"labels":{"alertname":"TestAlert","severity":"warning"},"annotations":{"summary":"Test alert"}}]'
   ```
