#!/usr/bin/env bash
# Usage: ./scripts/create-wave.sh --phase N --wave M [--from main]
#
# Creates a deployments branch for the given phase/wave, prunes stale
# worktrees, and pushes to origin.

set -euo pipefail

usage() {
    echo "Usage: $0 --phase N --wave M [--from BRANCH]"
    echo ""
    echo "Options:"
    echo "  --phase   Phase number (required)"
    echo "  --wave    Wave number (required)"
    echo "  --from    Base branch to create from (default: main)"
    exit 1
}

PHASE=""
WAVE=""
FROM="main"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --phase)  PHASE="$2"; shift 2 ;;
        --wave)   WAVE="$2"; shift 2 ;;
        --from)   FROM="$2"; shift 2 ;;
        -h|--help) usage ;;
        *)        echo "Unknown option: $1"; usage ;;
    esac
done

if [[ -z "$PHASE" || -z "$WAVE" ]]; then
    echo "ERROR: --phase and --wave are required."
    usage
fi

BRANCH="deployments/phase${PHASE}/wave-${WAVE}"

echo "Creating branch: $BRANCH from $FROM"

# Fetch latest
git fetch origin

# Create the branch from the base
git checkout "$FROM"
git pull origin "$FROM"
git checkout -b "$BRANCH"

# Prune stale worktrees
echo "Pruning stale worktrees..."
git worktree prune

# Push to origin
git push -u origin "$BRANCH"

echo "Branch $BRANCH created and pushed to origin."
