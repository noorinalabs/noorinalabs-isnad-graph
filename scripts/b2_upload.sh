#!/usr/bin/env bash
# Upload pipeline artifacts (staging/curated Parquet + manifest) to Backblaze B2.
#
# Manifest-aware: compares local .manifest.json against the remote copy in B2
# and only uploads files whose SHA256 hashes have changed.
#
# Required env vars:
#   B2_APPLICATION_KEY_ID  — Backblaze B2 key ID
#   B2_APPLICATION_KEY     — Backblaze B2 application key
#   B2_BUCKET_NAME         — Target B2 bucket name
#
# Usage:
#   B2_APPLICATION_KEY_ID=xxx B2_APPLICATION_KEY=yyy B2_BUCKET_NAME=zzz \
#     scripts/b2_upload.sh [--dry-run]
set -euo pipefail

DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
  esac
done

# --- Validate environment ---------------------------------------------------
for var in B2_APPLICATION_KEY_ID B2_APPLICATION_KEY B2_BUCKET_NAME; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: $var is not set" >&2
    exit 1
  fi
done

# --- Paths -------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFEST_FILE="$REPO_ROOT/.manifest.json"
B2_MANIFEST_PATH="pipeline/.manifest.json"

if [[ ! -f "$MANIFEST_FILE" ]]; then
  echo "ERROR: Local manifest not found at $MANIFEST_FILE" >&2
  echo "Run the pipeline manifest generation step first." >&2
  exit 1
fi

# --- Authorize B2 CLI --------------------------------------------------------
echo "Authorizing B2..."
b2 account authorize "$B2_APPLICATION_KEY_ID" "$B2_APPLICATION_KEY" > /dev/null

# --- Fetch remote manifest for diff -----------------------------------------
REMOTE_MANIFEST=""
TMPDIR_CLEAN=$(mktemp -d)
trap 'rm -rf "$TMPDIR_CLEAN"' EXIT

echo "Fetching remote manifest from B2..."
if b2 file download "b2://$B2_BUCKET_NAME/$B2_MANIFEST_PATH" "$TMPDIR_CLEAN/remote_manifest.json" 2>/dev/null; then
  REMOTE_MANIFEST="$TMPDIR_CLEAN/remote_manifest.json"
  echo "  Remote manifest retrieved."
else
  echo "  No remote manifest found — will upload all files."
fi

# --- Determine which files need uploading ------------------------------------
# Use Python to compare manifests (SHA256-based, matching pipeline.yml format)
CHANGED_FILES=$(python3 -c "
import json, sys

local = json.load(open('$MANIFEST_FILE'))
local_files = local.get('files', {})

remote_files = {}
remote_path = '$REMOTE_MANIFEST'
if remote_path:
    try:
        remote = json.load(open(remote_path))
        remote_files = remote.get('files', {})
    except (FileNotFoundError, json.JSONDecodeError):
        pass

changed = []
for path, info in local_files.items():
    remote_info = remote_files.get(path, {})
    if info.get('sha256') != remote_info.get('sha256'):
        changed.append(path)

# Always include manifest itself
print('\n'.join(changed))
")

TOTAL_LOCAL=$(python3 -c "
import json
m = json.load(open('$MANIFEST_FILE'))
print(len(m.get('files', {})))
")
CHANGED_COUNT=$(echo "$CHANGED_FILES" | grep -c '.' || true)

echo ""
echo "Local files:   $TOTAL_LOCAL"
echo "Changed files: $CHANGED_COUNT"

if [[ "$CHANGED_COUNT" -eq 0 ]]; then
  echo "All files up-to-date in B2. Nothing to upload."
  exit 0
fi

# --- Upload changed files ----------------------------------------------------
UPLOADED=0
FAILED=0

while IFS= read -r filepath; do
  [[ -z "$filepath" ]] && continue
  local_path="$REPO_ROOT/$filepath"
  b2_path="pipeline/$filepath"

  if [[ ! -f "$local_path" ]]; then
    echo "  SKIP (missing): $filepath"
    continue
  fi

  if [[ "$DRY_RUN" == "true" ]]; then
    echo "  [DRY RUN] Would upload: $filepath -> $b2_path"
    UPLOADED=$((UPLOADED + 1))
  else
    echo "  Uploading: $filepath -> $b2_path"
    if b2 file upload "$B2_BUCKET_NAME" "$local_path" "$b2_path" > /dev/null; then
      UPLOADED=$((UPLOADED + 1))
    else
      echo "  FAILED: $filepath" >&2
      FAILED=$((FAILED + 1))
    fi
  fi
done <<< "$CHANGED_FILES"

# --- Upload the manifest itself ----------------------------------------------
if [[ "$DRY_RUN" == "true" ]]; then
  echo "  [DRY RUN] Would upload: .manifest.json -> $B2_MANIFEST_PATH"
else
  echo "  Uploading: .manifest.json -> $B2_MANIFEST_PATH"
  b2 file upload "$B2_BUCKET_NAME" "$MANIFEST_FILE" "$B2_MANIFEST_PATH" > /dev/null
fi

# --- Summary -----------------------------------------------------------------
echo ""
PREFIX=""
[[ "$DRY_RUN" == "true" ]] && PREFIX="[DRY RUN] "
echo "${PREFIX}Upload complete: $UPLOADED uploaded, $FAILED failed out of $CHANGED_COUNT changed."

if [[ "$FAILED" -gt 0 ]]; then
  exit 1
fi
