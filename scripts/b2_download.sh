#!/usr/bin/env bash
# Download pipeline artifacts from Backblaze B2 to local data directory.
#
# Manifest-aware: compares remote .manifest.json against the local copy
# and only downloads files whose SHA256 hashes have changed.
#
# Required env vars:
#   B2_APPLICATION_KEY_ID  — Backblaze B2 key ID
#   B2_APPLICATION_KEY     — Backblaze B2 application key
#   B2_BUCKET_NAME         — Target B2 bucket name
#
# Usage:
#   B2_APPLICATION_KEY_ID=xxx B2_APPLICATION_KEY=yyy B2_BUCKET_NAME=zzz \
#     scripts/b2_download.sh [--dry-run]
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

TMPDIR_CLEAN=$(mktemp -d)
trap 'rm -rf "$TMPDIR_CLEAN"' EXIT

# --- Authorize B2 CLI --------------------------------------------------------
echo "Authorizing B2..."
b2 account authorize "$B2_APPLICATION_KEY_ID" "$B2_APPLICATION_KEY" > /dev/null

# --- Fetch remote manifest ---------------------------------------------------
echo "Fetching remote manifest from B2..."
REMOTE_MANIFEST="$TMPDIR_CLEAN/remote_manifest.json"
if ! b2 file download "b2://$B2_BUCKET_NAME/$B2_MANIFEST_PATH" "$REMOTE_MANIFEST" 2>/dev/null; then
  echo "ERROR: No remote manifest found in B2 bucket $B2_BUCKET_NAME" >&2
  echo "Has the pipeline been run and uploaded to B2?" >&2
  exit 1
fi
echo "  Remote manifest retrieved."

# --- Load local manifest (if exists) -----------------------------------------
LOCAL_MANIFEST=""
if [[ -f "$MANIFEST_FILE" ]]; then
  LOCAL_MANIFEST="$MANIFEST_FILE"
  echo "  Local manifest found."
else
  echo "  No local manifest — will download all files."
fi

# --- Determine which files need downloading ----------------------------------
CHANGED_FILES=$(python3 -c "
import json

remote = json.load(open('$REMOTE_MANIFEST'))
remote_files = remote.get('files', {})

local_files = {}
local_path = '$LOCAL_MANIFEST'
if local_path:
    try:
        local_data = json.load(open(local_path))
        local_files = local_data.get('files', {})
    except (FileNotFoundError, json.JSONDecodeError):
        pass

changed = []
for path, info in remote_files.items():
    local_info = local_files.get(path, {})
    if info.get('sha256') != local_info.get('sha256'):
        changed.append(path)

print('\n'.join(changed))
")

TOTAL_REMOTE=$(python3 -c "
import json
m = json.load(open('$REMOTE_MANIFEST'))
print(len(m.get('files', {})))
")
CHANGED_COUNT=$(echo "$CHANGED_FILES" | grep -c '.' || true)

echo ""
echo "Remote files:  $TOTAL_REMOTE"
echo "Changed files: $CHANGED_COUNT"

if [[ "$CHANGED_COUNT" -eq 0 ]]; then
  echo "All files up-to-date locally. Nothing to download."
  exit 0
fi

# --- Download changed files --------------------------------------------------
DOWNLOADED=0
FAILED=0

while IFS= read -r filepath; do
  [[ -z "$filepath" ]] && continue
  local_path="$REPO_ROOT/$filepath"
  b2_path="pipeline/$filepath"

  # Ensure target directory exists
  mkdir -p "$(dirname "$local_path")"

  if [[ "$DRY_RUN" == "true" ]]; then
    echo "  [DRY RUN] Would download: $b2_path -> $filepath"
    DOWNLOADED=$((DOWNLOADED + 1))
  else
    echo "  Downloading: $b2_path -> $filepath"
    if b2 file download "b2://$B2_BUCKET_NAME/$b2_path" "$local_path" 2>/dev/null; then
      DOWNLOADED=$((DOWNLOADED + 1))
    else
      echo "  FAILED: $filepath" >&2
      FAILED=$((FAILED + 1))
    fi
  fi
done <<< "$CHANGED_FILES"

# --- Update local manifest ---------------------------------------------------
if [[ "$DRY_RUN" == "true" ]]; then
  echo "  [DRY RUN] Would update local manifest"
else
  echo "  Updating local manifest..."
  cp "$REMOTE_MANIFEST" "$MANIFEST_FILE"
fi

# --- Summary -----------------------------------------------------------------
echo ""
PREFIX=""
[[ "$DRY_RUN" == "true" ]] && PREFIX="[DRY RUN] "
echo "${PREFIX}Download complete: $DOWNLOADED downloaded, $FAILED failed out of $CHANGED_COUNT changed."

if [[ "$FAILED" -gt 0 ]]; then
  exit 1
fi
