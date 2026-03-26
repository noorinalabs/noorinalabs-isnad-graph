#!/usr/bin/env bash
# =============================================================================
# isnad-graph restore script
# Downloads backups from Backblaze B2, verifies checksums, and restores
# PostgreSQL and Neo4j databases.
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
#   RESTORE_DIR     — Local restore staging directory (default: /tmp/isnad-restore)
#
# Usage:
#   ./scripts/restore.sh latest                    # Restore most recent backup
#   ./scripts/restore.sh daily/2026-03-25          # Restore specific date
#   ./scripts/restore.sh --force daily/2026-03-25  # Skip confirmation prompt
#   ./scripts/restore.sh --list                    # List available backups
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
POSTGRES_USER="${POSTGRES_USER:-isnad}"
POSTGRES_DB="${POSTGRES_DB:-isnad_graph}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
RESTORE_DIR="${RESTORE_DIR:-/tmp/isnad-restore}"

RCLONE_REMOTE="isnad"

: "${B2_KEY_ID:?B2_KEY_ID must be set}"
: "${B2_APP_KEY:?B2_APP_KEY must be set}"
: "${B2_BUCKET:?B2_BUCKET must be set}"

export RCLONE_CONFIG_ISNAD_TYPE="b2"
export RCLONE_CONFIG_ISNAD_ACCOUNT="${B2_KEY_ID}"
export RCLONE_CONFIG_ISNAD_KEY="${B2_APP_KEY}"

FORCE=false

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log() {
    local level="$1"
    shift
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [${level}] $*"
}

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
cleanup() {
    if [[ -d "$RESTORE_DIR" ]]; then
        rm -rf "$RESTORE_DIR"
        log "INFO" "Cleaned up restore staging directory"
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

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

list_backups() {
    log "INFO" "Available backups in ${B2_BUCKET}:"
    echo ""
    echo "=== Daily ==="
    rclone lsf "${RCLONE_REMOTE}:${B2_BUCKET}/daily/" --dirs-only 2>/dev/null || echo "  (none)"
    echo ""
    echo "=== Weekly ==="
    rclone lsf "${RCLONE_REMOTE}:${B2_BUCKET}/weekly/" --dirs-only 2>/dev/null || echo "  (none)"
}

resolve_latest() {
    # Find the most recent backup across daily and weekly
    local latest=""
    local latest_date="0000-00-00"

    for category in daily weekly; do
        local dirs
        dirs=$(rclone lsf "${RCLONE_REMOTE}:${B2_BUCKET}/${category}/" --dirs-only 2>/dev/null || true)
        while IFS= read -r dir; do
            [[ -z "$dir" ]] && continue
            dir="${dir%/}"
            if [[ "$dir" > "$latest_date" ]]; then
                latest_date="$dir"
                latest="${category}/${dir}"
            fi
        done <<< "$dirs"
    done

    if [[ -z "$latest" ]]; then
        log "ERROR" "No backups found in B2 bucket"
        exit 1
    fi

    echo "$latest"
}

verify_checksums() {
    local dir="$1"
    local all_ok=true

    log "INFO" "Verifying checksums..."
    for checksum_file in "${dir}"/*.sha256; do
        [[ -f "$checksum_file" ]] || continue
        local base_file="${checksum_file%.sha256}"
        if [[ -f "$base_file" ]]; then
            local expected actual
            expected=$(awk '{print $1}' "$checksum_file")
            actual=$(sha256sum "$base_file" | awk '{print $1}')
            if [[ "$expected" == "$actual" ]]; then
                log "INFO" "Checksum OK: $(basename "$base_file")"
            else
                log "ERROR" "Checksum MISMATCH: $(basename "$base_file")"
                all_ok=false
            fi
        else
            log "WARNING" "File referenced by checksum not found: $(basename "$base_file")"
        fi
    done

    if [[ "$all_ok" == "false" ]]; then
        log "ERROR" "Checksum verification failed — aborting restore"
        exit 1
    fi
}

terminate_pg_connections() {
    log "INFO" "Terminating active PostgreSQL connections to ${POSTGRES_DB}..."
    docker compose -f "$COMPOSE_FILE" exec -T postgres \
        psql -U "$POSTGRES_USER" -d postgres -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${POSTGRES_DB}' AND pid <> pg_backend_pid();" \
        2>/dev/null || true
}

restore_postgres() {
    local dump_file="$1"
    log "INFO" "Restoring PostgreSQL from $(basename "$dump_file")..."

    terminate_pg_connections

    if docker compose -f "$COMPOSE_FILE" exec -T postgres \
        pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists \
        < "$dump_file" 2>&1; then
        log "INFO" "PostgreSQL restore complete"
    else
        # pg_restore returns non-zero for warnings (e.g., "role already exists")
        # which are typically harmless with --clean --if-exists
        log "WARNING" "pg_restore finished with warnings (this is often normal with --clean)"
    fi
}

restore_neo4j() {
    local dump_file="$1"

    # Decompress if needed
    if [[ "$dump_file" == *.zst ]]; then
        log "INFO" "Decompressing Neo4j dump..."
        local decompressed="${dump_file%.zst}"
        zstd -d "$dump_file" -o "$decompressed"
        dump_file="$decompressed"
    fi

    log "INFO" "Stopping Neo4j for restore..."
    docker compose -f "$COMPOSE_FILE" stop neo4j

    # Wait for Neo4j to stop
    local max_wait=30 waited=0
    while docker compose -f "$COMPOSE_FILE" ps --format '{{.Service}}:{{.State}}' 2>/dev/null | grep -q "neo4j:running"; do
        if [[ $waited -ge $max_wait ]]; then
            log "ERROR" "Neo4j did not stop within ${max_wait}s"
            exit 1
        fi
        sleep 1
        waited=$((waited + 1))
    done

    NEO4J_VOLUME=$(docker volume ls --format '{{.Name}}' | grep -E '(neo4j_data|neo4j-data)$' | head -1)
    if [[ -z "$NEO4J_VOLUME" ]]; then
        log "ERROR" "Cannot find Neo4j data volume"
        docker compose -f "$COMPOSE_FILE" up -d neo4j
        exit 1
    fi

    local dump_dir
    dump_dir=$(dirname "$dump_file")
    local dump_basename
    dump_basename=$(basename "$dump_file")

    log "INFO" "Loading Neo4j dump..."
    if docker run --rm \
        -v "${NEO4J_VOLUME}:/data" \
        -v "${dump_dir}:/backups" \
        neo4j:5-community \
        neo4j-admin database load neo4j --from-path=/backups/ --overwrite-destination 2>&1; then
        log "INFO" "Neo4j restore complete"
    else
        log "ERROR" "Neo4j restore failed"
        docker compose -f "$COMPOSE_FILE" up -d neo4j
        exit 1
    fi

    log "INFO" "Restarting Neo4j..."
    docker compose -f "$COMPOSE_FILE" up -d neo4j

    # Wait for healthy
    local max_health=120 health_waited=0
    while ! docker compose -f "$COMPOSE_FILE" ps --format '{{.Service}}:{{.Health}}' 2>/dev/null | grep -q "neo4j:healthy"; do
        if [[ $health_waited -ge $max_health ]]; then
            log "WARNING" "Neo4j did not become healthy within ${max_health}s"
            break
        fi
        sleep 5
        health_waited=$((health_waited + 5))
    done
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
BACKUP_PATH=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)
            FORCE=true
            shift
            ;;
        --list)
            list_backups
            exit 0
            ;;
        --help|-h)
            echo "Usage: $0 [--force] [--list] <backup-path|latest>"
            echo ""
            echo "  latest              Restore the most recent backup"
            echo "  daily/2026-03-25    Restore a specific backup"
            echo "  --force             Skip confirmation prompt"
            echo "  --list              List available backups"
            exit 0
            ;;
        *)
            BACKUP_PATH="$1"
            shift
            ;;
    esac
done

if [[ -z "$BACKUP_PATH" ]]; then
    echo "Usage: $0 [--force] [--list] <backup-path|latest>"
    echo "Run '$0 --list' to see available backups."
    exit 1
fi

# ---------------------------------------------------------------------------
# Resolve backup path
# ---------------------------------------------------------------------------
if [[ "$BACKUP_PATH" == "latest" ]]; then
    BACKUP_PATH=$(resolve_latest)
    log "INFO" "Resolved 'latest' to: ${BACKUP_PATH}"
fi

# ---------------------------------------------------------------------------
# Confirmation prompt
# ---------------------------------------------------------------------------
if [[ "$FORCE" == "false" ]]; then
    echo ""
    echo "========================================================"
    echo "  WARNING: This will OVERWRITE the current databases."
    echo ""
    echo "  Backup source: ${RCLONE_REMOTE}:${B2_BUCKET}/${BACKUP_PATH}/"
    echo "  PostgreSQL DB: ${POSTGRES_DB}"
    echo "  Neo4j:         will be stopped and restored"
    echo "========================================================"
    echo ""
    read -r -p "Type YES to confirm restore: " confirm
    if [[ "$confirm" != "YES" ]]; then
        log "INFO" "Restore cancelled by user"
        exit 0
    fi
fi

# ---------------------------------------------------------------------------
# Download backup
# ---------------------------------------------------------------------------
mkdir -p "$RESTORE_DIR"

log "INFO" "Downloading backup from ${RCLONE_REMOTE}:${B2_BUCKET}/${BACKUP_PATH}/..."
if ! rclone copy "${RCLONE_REMOTE}:${B2_BUCKET}/${BACKUP_PATH}/" "$RESTORE_DIR/" --log-level INFO; then
    log "ERROR" "Failed to download backup from B2"
    exit 1
fi

# ---------------------------------------------------------------------------
# Verify checksums
# ---------------------------------------------------------------------------
verify_checksums "$RESTORE_DIR"

# ---------------------------------------------------------------------------
# Restore databases
# ---------------------------------------------------------------------------

# Find dump files
PG_DUMP=$(find "$RESTORE_DIR" -name 'isnad-pg-*.dump' -type f | head -1)
NEO4J_DUMP=$(find "$RESTORE_DIR" \( -name 'isnad-neo4j-*.dump.zst' -o -name 'isnad-neo4j-*.dump' \) -type f | head -1)

if [[ -n "$PG_DUMP" ]]; then
    restore_postgres "$PG_DUMP"
else
    log "WARNING" "No PostgreSQL dump found in backup"
fi

if [[ -n "$NEO4J_DUMP" ]]; then
    restore_neo4j "$NEO4J_DUMP"
else
    log "WARNING" "No Neo4j dump found in backup"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
log "INFO" "=== Restore complete ==="
log "INFO" "Source: ${RCLONE_REMOTE}:${B2_BUCKET}/${BACKUP_PATH}/"
log "INFO" "PostgreSQL: $(if [[ -n "$PG_DUMP" ]]; then echo "restored"; else echo "skipped (no dump)"; fi)"
log "INFO" "Neo4j:      $(if [[ -n "$NEO4J_DUMP" ]]; then echo "restored"; else echo "skipped (no dump)"; fi)"
