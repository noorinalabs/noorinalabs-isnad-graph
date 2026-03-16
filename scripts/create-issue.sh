#!/usr/bin/env bash
# Usage: ./scripts/create-issue.sh --type feature|bug|tech-debt --phase N --assignee FIRSTNAME_LASTNAME --title "..." --body "..."
#
# Creates a GitHub issue with proper labels based on type and phase.

set -euo pipefail

usage() {
    echo "Usage: $0 --type feature|bug|tech-debt --phase N --assignee FIRSTNAME_LASTNAME --title \"...\" [--body \"...\"]"
    echo ""
    echo "Options:"
    echo "  --type       Issue type: feature, bug, or tech-debt"
    echo "  --phase      Phase number (e.g., 3)"
    echo "  --assignee   GitHub username or FIRSTNAME_LASTNAME"
    echo "  --title      Issue title (required)"
    echo "  --body       Issue body (optional)"
    exit 1
}

TYPE=""
PHASE=""
ASSIGNEE=""
TITLE=""
BODY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --type)     TYPE="$2"; shift 2 ;;
        --phase)    PHASE="$2"; shift 2 ;;
        --assignee) ASSIGNEE="$2"; shift 2 ;;
        --title)    TITLE="$2"; shift 2 ;;
        --body)     BODY="$2"; shift 2 ;;
        -h|--help)  usage ;;
        *)          echo "Unknown option: $1"; usage ;;
    esac
done

if [[ -z "$TYPE" || -z "$PHASE" || -z "$ASSIGNEE" || -z "$TITLE" ]]; then
    echo "ERROR: --type, --phase, --assignee, and --title are required."
    usage
fi

# Validate type
case "$TYPE" in
    feature|bug|tech-debt) ;;
    *) echo "ERROR: --type must be one of: feature, bug, tech-debt"; exit 1 ;;
esac

# Build labels
LABELS="${TYPE},phase${PHASE}"

if [[ "$TYPE" == "bug" ]]; then
    LABELS="${LABELS},found-in-phase${PHASE}"
fi

# Build gh command
CMD=(gh issue create --title "$TITLE" --label "$LABELS" --assignee "$ASSIGNEE")

if [[ -n "$BODY" ]]; then
    CMD+=(--body "$BODY")
fi

echo "Creating $TYPE issue for phase $PHASE..."
"${CMD[@]}"
