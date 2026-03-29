# Rollback Test Procedure

Manual test procedure for validating the backup/restore and rollback pipeline.

## Prerequisites

- SSH access to the VPS as the `deploy` user
- B2 credentials configured (`B2_KEY_ID`, `B2_APP_KEY`, `B2_BUCKET`)
- A recent backup exists (check with `restore.sh --list`)
- All VPS tools installed: `docker`, `rclone`, `zstd`, `sha256sum`, `git`

## 1. Verify backup exists

```bash
ssh deploy@isnad-graph.noorinalabs.com
cd /opt/isnad-graph
export B2_KEY_ID="..." B2_APP_KEY="..." B2_BUCKET="..."
bash scripts/restore.sh --list
```

Confirm at least one daily or weekly backup is listed.

## 2. Dry-run restore validation

The `--dry-run` flag downloads and validates the backup without overwriting any data:

```bash
bash scripts/restore.sh --dry-run latest
```

Expected output:
- Download succeeds
- All SHA256 checksums pass
- Both PostgreSQL and Neo4j dump files are present and non-empty
- Script exits with `DRY RUN complete -- no data was modified`

## 3. Full restore test (staging or maintenance window)

**WARNING:** This overwrites live databases. Only run during a maintenance window or on a staging environment.

### 3a. Record current state

Before restoring, capture the current database state for comparison:

```bash
# Record PG row counts
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U isnad -d isnad_graph -c "SELECT schemaname, relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 20;"

# Record Neo4j node counts
docker compose -f docker-compose.prod.yml exec -T neo4j \
  cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS cnt ORDER BY cnt DESC;"
```

### 3b. Create a fresh backup

```bash
bash scripts/backup.sh
```

### 3c. Restore from the backup just created

```bash
bash scripts/restore.sh --force latest
```

### 3d. Verify restore

```bash
# Check PG row counts match pre-restore state
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U isnad -d isnad_graph -c "SELECT schemaname, relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 20;"

# Check Neo4j node counts match
docker compose -f docker-compose.prod.yml exec -T neo4j \
  cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS cnt ORDER BY cnt DESC;"

# Verify API health
curl -s http://localhost:8000/health | jq .
```

## 4. Code rollback test

Test that the deploy workflow's automatic rollback restores both code and data:

```bash
# Check the stored pre-deploy SHA
cat /opt/isnad-graph/.last-deploy-sha

# Simulate code rollback
git log --oneline -5
PREVIOUS_SHA=$(cat /opt/isnad-graph/.last-deploy-sha)
echo "Would roll back to: ${PREVIOUS_SHA}"
```

To test via the Restore workflow, trigger it from GitHub Actions with `rollback_code: true`.

## Restore ordering

The restore process follows a specific order:

1. **PostgreSQL first** -- graph loaders assume PG metadata exists when populating Neo4j relationships (Elena's feedback from PR #427)
2. **Neo4j second** -- Neo4j must be stopped for offline restore, then restarted
3. **API last** -- brought up after both databases are verified healthy

This ordering is enforced by both `restore.sh` and the deploy workflow's automatic rollback step.

## Automated rollback (deploy workflow)

The deploy workflow (`deploy.yml`) automatically triggers rollback when:

1. The health check step fails after deploy
2. A pre-deploy backup was successfully created

The automatic rollback:
1. Reads the previous commit SHA from `.last-deploy-sha`
2. Resets the code to that commit (`git reset --hard`)
3. Stops all containers
4. Brings up only PG and Neo4j
5. Runs `restore.sh --force latest`
6. Rebuilds and brings up all services

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|-------------|--------|
| `restore.sh` fails on download | B2 credentials expired or bucket name wrong | Re-export `B2_KEY_ID`, `B2_APP_KEY`, `B2_BUCKET` |
| Checksum mismatch | Corrupt upload or incomplete download | Re-run backup, then retry restore |
| Neo4j won't stop | Container hung | `docker compose -f docker-compose.prod.yml kill neo4j` then retry |
| PG restore warnings | Normal with `--clean --if-exists` | Check for actual errors in output; warnings about "role already exists" are harmless |
| Neo4j unhealthy after restore | Database version mismatch | Verify Neo4j image version matches the one used for backup |
| `.last-deploy-sha` missing | First deploy or file was deleted | Code rollback will be skipped; only data is restored |
