#!/usr/bin/env bash
# Fail if frontend/package-lock.json contains absolute local paths (file:///tmp/, /home/, etc.).
# These break CI because the resolved paths only exist on the developer's machine.
set -euo pipefail

LOCKFILE="frontend/package-lock.json"
PATTERN='"resolved":[[:space:]]*"file://(/tmp/|/home/|/Users/|/var/)'

if [[ ! -f "$LOCKFILE" ]]; then
  exit 0
fi

if grep -qE "$PATTERN" "$LOCKFILE"; then
  echo "ERROR: $LOCKFILE contains absolute local paths (file:///tmp/, /home/, /Users/, /var/)."
  echo "These break CI. Run npm install with the correct dependency source."
  grep -nE "$PATTERN" "$LOCKFILE" | head -5
  exit 1
fi
