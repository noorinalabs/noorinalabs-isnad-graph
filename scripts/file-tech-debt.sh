#!/usr/bin/env bash
# Usage: ./scripts/file-tech-debt.sh --title "..." --assignee FIRSTNAME_LASTNAME --found-in "phase7-wave2" --next-phase 8
#
# Creates a tech-debt issue with proper labels for tracking.

set -euo pipefail

usage() {
    echo "Usage: $0 --title \"...\" --assignee FIRSTNAME_LASTNAME --found-in \"phaseN-waveM\" --next-phase N [--body \"...\"]"
    echo ""
    echo "Options:"
    echo "  --title       Issue title (required)"
    echo "  --assignee    GitHub username or FIRSTNAME_LASTNAME (required)"
    echo "  --found-in    Where the debt was found, e.g. phase7-wave2 (required)"
    echo "  --next-phase  Phase to address the debt (required)"
    echo "  --body        Issue body (optional)"
    exit 1
}

TITLE=""
ASSIGNEE=""
FOUND_IN=""
NEXT_PHASE=""
BODY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --title)      TITLE="$2"; shift 2 ;;
        --assignee)   ASSIGNEE="$2"; shift 2 ;;
        --found-in)   FOUND_IN="$2"; shift 2 ;;
        --next-phase) NEXT_PHASE="$2"; shift 2 ;;
        --body)       BODY="$2"; shift 2 ;;
        -h|--help)    usage ;;
        *)            echo "Unknown option: $1"; usage ;;
    esac
done

if [[ -z "$TITLE" || -z "$ASSIGNEE" || -z "$FOUND_IN" || -z "$NEXT_PHASE" ]]; then
    echo "ERROR: --title, --assignee, --found-in, and --next-phase are required."
    usage
fi

LABELS="tech-debt,found-in-${FOUND_IN},phase${NEXT_PHASE}"

CMD=(gh issue create --title "$TITLE" --label "$LABELS" --assignee "$ASSIGNEE")

if [[ -n "$BODY" ]]; then
    CMD+=(--body "$BODY")
else
    CMD+=(--body "Tech debt identified in ${FOUND_IN}. Scheduled for phase ${NEXT_PHASE}.")
fi

echo "Filing tech-debt issue: $TITLE"
"${CMD[@]}"
