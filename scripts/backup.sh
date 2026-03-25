#!/usr/bin/env bash
# =============================================================================
# isnad-graph automated backup script
# Dumps PostgreSQL and Neo4j databases, compresses, checksums, and uploads
# to Backblaze B2 via rclone. Manages retention (7 daily + 4 weekly).
#
# Required environment variables:
#   B2_KEY_ID       — Backblaze B2 application key ID
#   B2_APP_KEY      — Backblaze B2 application key
#   B2_BUCKET       — Backblaze B2 bucket name
#
# Optional environment variables:
#   POSTGRES_USER   — PostgreSQL user (default: isnad)
#   POSTGRES_DB     — PostgreSQL database (default: isnad_graph)
#   COMPOSE_FILE    — Docker Compose file (default: docker-compose.prod.yml)
#   BACKUP_DIR      — Local backup staging directory (default: /tmp/isnad-backups)
#   DAILY_RETAIN    — Number of daily backups to keep (default: 7)
#   WEEKLY_RETAIN   — Number of weekly backups to keep (default: 4)
#   DRY_RUN         — Set to "true" to show what would be pruned without deleting
#
# Usage:
#   ./scripts/backup.sh
#   DRY_RUN=true ./scripts/backup.sh
# =============================================================================
set -euo pipefail

# Restrict file permissions — backups contain sensitive database dumps
umask 077

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
POSTGRES_USER="${POSTGRES_USER:-isnad}"
POSTGRES_DB="${POSTGRES_DB:-isnad_graph}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-$(mktemp -d /tmp/isnad-backups.XXXXXXXXXX)}"
DAILY_RETAIN="${DAILY_RETAIN:-7}"
WEEKLY_RETAIN="${WEEKLY_RETAIN:-4}"
DRY_RUN="${DRY_RUN:-false}"

TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
DATE_STAMP="$(date -u +%Y-%m-%d)"
DAY_OF_WEEK="$(date -u +%u)"  # 1=Monday, 7=Sunday

# Backup category: weekly on Sundays, daily otherwise
if [[ "$DAY_OF_WEEK" -eq 7 ]]; then
    BACKUP_CATEGORY="weekly"
else
    BACKUP_CATEGORY="daily"
fi

BACKUP_SUBDIR="${BACKUP_CATEGORY}/${DATE_STAMP}"
LOCAL_BACKUP_PATH="${BACKUP_DIR}/${BACKUP_SUBDIR}"

# rclone remote name (configured via env vars)
RCLONE_REMOTE="isnad"

# Required environment variables
: "${B2_KEY_ID:?B2_KEY_ID must be set}"
: "${B2_APP_KEY:?B2_APP_KEY must be set}"
: "${B2_BUCKET:?B2_BUCKET must be set}"

# Export rclone native env vars for credential-safe operation (no CLI flags)
export RCLONE_CONFIG_ISNAD_TYPE="b2"
export RCLONE_CONFIG_ISNAD_ACCOUNT="${B2_KEY_ID}"
export RCLONE_CONFIG_ISNAD_KEY="${B2_APP_KEY}"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE="${BACKUP_DIR}/backup-${TIMESTAMP}.log"

log() {
    local level="$1"
    shift
    local msg
    msg="$(date -u +%Y-%m-%dT%H:%M:%SZ) [${level}] $*"
    echo "$msg" | tee -a "$LOG_FILE"
}

# ---------------------------------------------------------------------------
# Cleanup handler
# ---------------------------------------------------------------------------
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        log "ERROR" "Backup script exited with code ${exit_code}"
    fi
    # Clean up entire staging directory to avoid leaving sensitive dumps on disk
    if [[ -d "$BACKUP_DIR" ]]; then
        rm -rf "$BACKUP_DIR"
        log "INFO" "Cleaned up backup staging directory: ${BACKUP_DIR}"
    fi
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
for cmd in docker rclone zstd sha256sum; do
    if ! command -v "$cmd" &>/dev/null; then
        log "ERROR" "Required command not found: ${cmd}"
        exit 1
    fi
done

if ! docker compose -f "$COMPOSE_FILE" ps --format json &>/dev/null; then
    log "ERROR" "Cannot reach Docker Compose services (is Docker running?)"
    exit 1
fi

mkdir -p "$LOCAL_BACKUP_PATH"
mkdir -p "$(dirname "$LOG_FILE")"

log "INFO" "=== Backup started (${BACKUP_CATEGORY}) ==="
log "INFO" "Timestamp: ${TIMESTAMP}"
log "INFO" "Local staging: ${LOCAL_BACKUP_PATH}"
log "INFO" "Remote target: ${RCLONE_REMOTE}:${B2_BUCKET}/${BACKUP_SUBDIR}"

PG_OK=false
NEO4J_OK=false

# ---------------------------------------------------------------------------
# 1. PostgreSQL dump
# ---------------------------------------------------------------------------
PG_DUMP_FILE="${LOCAL_BACKUP_PATH}/isnad-pg-${TIMESTAMP}.dump"

log "INFO" "Starting PostgreSQL dump..."
if docker compose -f "$COMPOSE_FILE" exec -T postgres \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom \
    > "$PG_DUMP_FILE" 2>>"$LOG_FILE"; then

    PG_SIZE=$(stat -c%s "$PG_DUMP_FILE" 2>/dev/null || stat -f%z "$PG_DUMP_FILE" 2>/dev/null)
    if [[ "$PG_SIZE" -gt 0 ]]; then
        log "INFO" "PostgreSQL dump complete: $(du -h "$PG_DUMP_FILE" | cut -f1)"
        PG_OK=true
    else
        log "ERROR" "PostgreSQL dump produced empty file"
        rm -f "$PG_DUMP_FILE"
    fi
else
    log "ERROR" "PostgreSQL dump failed"
    rm -f "$PG_DUMP_FILE"
fi

# ---------------------------------------------------------------------------
# 2. Neo4j dump (stop → dump → restart)
# ---------------------------------------------------------------------------
NEO4J_DUMP_FILE="${LOCAL_BACKUP_PATH}/isnad-neo4j-${TIMESTAMP}.dump"
NEO4J_COMPRESSED="${NEO4J_DUMP_FILE}.zst"

log "INFO" "Stopping Neo4j for offline dump..."
docker compose -f "$COMPOSE_FILE" stop neo4j 2>>"$LOG_FILE"

# Wait for Neo4j container to fully stop
MAX_WAIT=30
WAITED=0
while docker compose -f "$COMPOSE_FILE" ps --format '{{.Service}}:{{.State}}' 2>/dev/null | grep -q "neo4j:running"; do
    if [[ $WAITED -ge $MAX_WAIT ]]; then
        log "ERROR" "Neo4j did not stop within ${MAX_WAIT}s"
        docker compose -f "$COMPOSE_FILE" up -d neo4j 2>>"$LOG_FILE"
        break
    fi
    sleep 1
    WAITED=$((WAITED + 1))
done

if [[ $WAITED -lt $MAX_WAIT ]]; then
    log "INFO" "Neo4j stopped (waited ${WAITED}s). Running dump..."

    # Determine the volume name (compose project prefix + volume name)
    NEO4J_VOLUME=$(docker volume ls --format '{{.Name}}' | grep -E '(neo4j_data|neo4j-data)$' | head -1)
    if [[ -z "$NEO4J_VOLUME" ]]; then
        log "ERROR" "Cannot find Neo4j data volume"
    else
        # Use bare docker run (not compose run) to avoid service config conflicts
        if docker run --rm \
            -v "${NEO4J_VOLUME}:/data" \
            -v "${LOCAL_BACKUP_PATH}:/backups" \
            neo4j:5-community \
            neo4j-admin database dump neo4j --to-path=/backups/ 2>>"$LOG_FILE"; then

            # The dump command outputs to /backups/neo4j.dump — rename it
            if [[ -f "${LOCAL_BACKUP_PATH}/neo4j.dump" ]]; then
                mv "${LOCAL_BACKUP_PATH}/neo4j.dump" "$NEO4J_DUMP_FILE"
            fi

            if [[ -f "$NEO4J_DUMP_FILE" ]]; then
                log "INFO" "Neo4j dump complete: $(du -h "$NEO4J_DUMP_FILE" | cut -f1)"

                # Compress with zstd
                log "INFO" "Compressing Neo4j dump with zstd..."
                zstd -3 --rm "$NEO4J_DUMP_FILE" -o "$NEO4J_COMPRESSED" 2>>"$LOG_FILE"
                log "INFO" "Compressed: $(du -h "$NEO4J_COMPRESSED" | cut -f1)"
                NEO4J_OK=true
            else
                log "ERROR" "Neo4j dump file not found after dump command"
            fi
        else
            log "ERROR" "Neo4j dump command failed"
        fi
    fi

    # Always restart Neo4j
    log "INFO" "Restarting Neo4j..."
    docker compose -f "$COMPOSE_FILE" up -d neo4j 2>>"$LOG_FILE"

    # Wait for Neo4j to become healthy
    MAX_HEALTH_WAIT=120
    HEALTH_WAITED=0
    while ! docker compose -f "$COMPOSE_FILE" ps --format '{{.Service}}:{{.Health}}' 2>/dev/null | grep -q "neo4j:healthy"; do
        if [[ $HEALTH_WAITED -ge $MAX_HEALTH_WAIT ]]; then
            log "WARNING" "Neo4j did not become healthy within ${MAX_HEALTH_WAIT}s — check manually"
            break
        fi
        sleep 5
        HEALTH_WAITED=$((HEALTH_WAITED + 5))
    done

    if [[ $HEALTH_WAITED -lt $MAX_HEALTH_WAIT ]]; then
        log "INFO" "Neo4j healthy (waited ${HEALTH_WAITED}s)"
    fi
else
    log "WARNING" "Skipped Neo4j dump due to stop timeout"
fi

# ---------------------------------------------------------------------------
# 3. Generate SHA256 checksums
# ---------------------------------------------------------------------------
log "INFO" "Generating SHA256 checksums..."
for f in "$LOCAL_BACKUP_PATH"/isnad-*; do
    [[ -f "$f" ]] || continue
    sha256sum "$f" | sed "s|${LOCAL_BACKUP_PATH}/||" > "${f}.sha256"
    log "INFO" "Checksum: $(basename "${f}.sha256")"
done

# ---------------------------------------------------------------------------
# 4. Upload to Backblaze B2
# ---------------------------------------------------------------------------
if [[ "$PG_OK" == "false" && "$NEO4J_OK" == "false" ]]; then
    log "ERROR" "Both PostgreSQL and Neo4j dumps failed — nothing to upload"
    exit 1
fi

if [[ "$PG_OK" == "false" || "$NEO4J_OK" == "false" ]]; then
    log "WARNING" "Partial backup — uploading available dumps only"
fi

log "INFO" "Uploading to B2: ${RCLONE_REMOTE}:${B2_BUCKET}/${BACKUP_SUBDIR}/"
if rclone copy "$LOCAL_BACKUP_PATH" "${RCLONE_REMOTE}:${B2_BUCKET}/${BACKUP_SUBDIR}/" \
    --log-level INFO 2>>"$LOG_FILE"; then
    log "INFO" "Upload complete"
else
    log "ERROR" "Upload to B2 failed"
    exit 1
fi

# ---------------------------------------------------------------------------
# 5. Retention pruning (deterministic, date-stamped directory based)
# ---------------------------------------------------------------------------
log "INFO" "Running retention pruning..."

prune_old_backups() {
    local category="$1"
    local retain_days="$2"
    local cutoff_epoch
    cutoff_epoch=$(date -u -d "${retain_days} days ago" +%s 2>/dev/null) || \
    cutoff_epoch=$(date -u -v-"${retain_days}"d +%s 2>/dev/null)

    # List date-stamped directories under the category
    local dirs
    dirs=$(rclone lsf "${RCLONE_REMOTE}:${B2_BUCKET}/${category}/" --dirs-only 2>/dev/null || true)

    while IFS= read -r dir; do
        [[ -z "$dir" ]] && continue
        # Strip trailing slash
        dir="${dir%/}"

        # Parse date from directory name (YYYY-MM-DD)
        if [[ "$dir" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
            local dir_epoch
            dir_epoch=$(date -u -d "$dir" +%s 2>/dev/null) || \
            dir_epoch=$(date -u -j -f "%Y-%m-%d" "$dir" +%s 2>/dev/null) || continue

            if [[ "$dir_epoch" -lt "$cutoff_epoch" ]]; then
                if [[ "$DRY_RUN" == "true" ]]; then
                    log "INFO" "[DRY RUN] Would prune: ${category}/${dir}/"
                else
                    log "INFO" "Pruning: ${category}/${dir}/"
                    rclone purge "${RCLONE_REMOTE}:${B2_BUCKET}/${category}/${dir}/" 2>>"$LOG_FILE" || \
                        log "WARNING" "Failed to prune ${category}/${dir}/"
                fi
            fi
        fi
    done <<< "$dirs"
}

prune_old_backups "daily" "$DAILY_RETAIN"
prune_old_backups "weekly" "$((WEEKLY_RETAIN * 7))"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
log "INFO" "=== Backup summary ==="
log "INFO" "PostgreSQL: $(if $PG_OK; then echo "OK"; else echo "FAILED"; fi)"
log "INFO" "Neo4j:      $(if $NEO4J_OK; then echo "OK"; else echo "FAILED"; fi)"
log "INFO" "Category:   ${BACKUP_CATEGORY}"
log "INFO" "Remote:     ${RCLONE_REMOTE}:${B2_BUCKET}/${BACKUP_SUBDIR}/"
log "INFO" "=== Backup finished ==="

if [[ "$PG_OK" == "false" || "$NEO4J_OK" == "false" ]]; then
    exit 1
fi
