#!/usr/bin/env bash
# run_full_pipeline.sh — Full data ingestion pipeline orchestrator
#
# Runs all pipeline stages in order with error handling and timeouts.
# Designed for production use on the VPS or local development.
#
# Usage:
#   bash scripts/run_full_pipeline.sh [OPTIONS]
#
# Options:
#   --skip-acquire    Skip the acquire stage (use existing raw data)
#   --skip-resolve    Skip the resolve stage (NER + disambiguate + dedup)
#   --skip-enrich     Skip the enrich stage (metrics, topics, historical)
#   --dry-run         Print what would be executed without running
#   --help            Show this help message
#
# Stage dependency matrix:
#   acquire           — no external services required (network only)
#   parse             — no external services required
#   validate-staging  — no external services required
#   resolve           — no external services required (CPU/GPU intensive)
#   load              — requires Neo4j
#   enrich            — requires Neo4j
#
# Environment:
#   ACQUIRE_TIMEOUT   — per-source timeout in seconds (default: 600)
#   PIPELINE_LOG_DIR  — directory for pipeline logs (default: data/logs)

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ACQUIRE_TIMEOUT="${ACQUIRE_TIMEOUT:-600}"
PIPELINE_LOG_DIR="${PIPELINE_LOG_DIR:-data/logs}"

SKIP_ACQUIRE=false
SKIP_RESOLVE=false
SKIP_ENRICH=false
DRY_RUN=false

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-acquire)
            SKIP_ACQUIRE=true
            shift
            ;;
        --skip-resolve)
            SKIP_RESOLVE=true
            shift
            ;;
        --skip-enrich)
            SKIP_ENRICH=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            head -n 22 "$0" | tail -n +2 | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option: $1"
            echo "Run with --help for usage."
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$PIPELINE_LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

run_stage() {
    local stage_name="$1"
    shift
    local cmd=("$@")

    log "=== STAGE: $stage_name ==="

    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would execute: ${cmd[*]}"
        return 0
    fi

    local logfile="$PIPELINE_LOG_DIR/${TIMESTAMP}_${stage_name}.log"
    local start_time
    start_time=$(date +%s)

    if "${cmd[@]}" 2>&1 | tee "$logfile"; then
        local end_time
        end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log "PASS: $stage_name completed in ${duration}s"
        return 0
    else
        local exit_code=$?
        local end_time
        end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log "FAIL: $stage_name failed after ${duration}s (exit code: $exit_code)"
        log "See log: $logfile"
        return $exit_code
    fi
}

# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------
log "Pipeline started at $(date)"
log "Options: skip-acquire=$SKIP_ACQUIRE skip-resolve=$SKIP_RESOLVE skip-enrich=$SKIP_ENRICH dry-run=$DRY_RUN"
log ""

FAILED_STAGES=()

# Stage 1: Acquire (no external services needed, network only)
if [[ "$SKIP_ACQUIRE" == "false" ]]; then
    if ! run_stage "acquire" timeout "${ACQUIRE_TIMEOUT}" uv run isnad acquire; then
        FAILED_STAGES+=("acquire")
        log "WARNING: acquire failed, but continuing — parse will use existing raw data"
    fi
else
    log "SKIP: acquire (--skip-acquire)"
fi

# Stage 2: Parse (no external services needed)
if ! run_stage "parse" uv run isnad parse; then
    FAILED_STAGES+=("parse")
    log "ERROR: parse failed — cannot continue without staging data"
    exit 1
fi

# Stage 3: Validate staging (no external services needed)
if ! run_stage "validate-staging" uv run isnad validate-staging; then
    FAILED_STAGES+=("validate-staging")
    log "WARNING: staging validation reported issues — continuing anyway"
fi

# Stage 4: Resolve — NER + disambiguate + dedup (no external services needed, CPU intensive)
if [[ "$SKIP_RESOLVE" == "false" ]]; then
    if ! run_stage "resolve" uv run isnad resolve; then
        FAILED_STAGES+=("resolve")
        log "ERROR: resolve failed — cannot load graph without resolved entities"
        exit 1
    fi
else
    log "SKIP: resolve (--skip-resolve)"
fi

# Stage 5: Load (requires Neo4j)
if ! run_stage "load" uv run isnad load; then
    FAILED_STAGES+=("load")
    log "ERROR: load failed — cannot enrich without loaded graph"
    exit 1
fi

# Stage 6: Enrich (requires Neo4j)
if [[ "$SKIP_ENRICH" == "false" ]]; then
    if ! run_stage "enrich" uv run isnad enrich; then
        FAILED_STAGES+=("enrich")
        log "WARNING: enrich failed — graph is loaded but not enriched"
    fi
else
    log "SKIP: enrich (--skip-enrich)"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
log ""
log "=== PIPELINE SUMMARY ==="
if [[ ${#FAILED_STAGES[@]} -eq 0 ]]; then
    log "All stages completed successfully."
else
    log "Failed stages: ${FAILED_STAGES[*]}"
    log "Pipeline completed with errors."
    exit 1
fi
