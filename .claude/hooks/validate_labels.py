#!/usr/bin/env python3
"""PreToolUse hook: Validate labels before gh issue create.

Extracts --label values from `gh issue create` commands and verifies each
label exists in the repository. Blocks execution if any label is missing.

Exit codes:
  0 — allow (not gh issue create, or all labels exist)
  2 — block (missing labels detected)
"""

import json
import re
import subprocess
import sys


def get_existing_labels() -> set[str]:
    """Fetch all existing labels from the repository."""
    try:
        result = subprocess.run(
            ["gh", "label", "list", "--limit", "500", "--json", "name"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return set()
        labels_data = json.loads(result.stdout)
        return {label["name"] for label in labels_data}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return set()


def extract_labels(command: str) -> list[str]:
    """Extract all --label and -l values from a gh issue create command."""
    labels = []

    # Match --label "value" or --label value or -l "value" or -l value
    # Also handles comma-separated labels in a single --label flag
    for match in re.finditer(r'(?:--label|-l)\s+["\']?([^"\']+?)["\']?(?:\s|$)', command):
        raw = match.group(1).strip()
        # gh CLI accepts comma-separated labels
        for label in raw.split(","):
            label = label.strip()
            if label:
                labels.append(label)

    return labels


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    command = input_data.get("tool_input", {}).get("command", "")

    # Only match gh issue create commands
    if not re.search(r"\bgh\s+issue\s+create\b", command):
        sys.exit(0)

    # Extract labels from the command
    labels = extract_labels(command)
    if not labels:
        sys.exit(0)

    # Fetch existing labels
    existing = get_existing_labels()
    if not existing:
        # If we can't fetch labels (network issue, etc.), allow with a warning
        result = {
            "decision": "allow",
            "systemMessage": (
                "WARNING: Could not fetch existing labels to validate. "
                "Proceeding without validation. Run `gh label list` to verify."
            ),
        }
        print(json.dumps(result))
        sys.exit(0)

    # Check for missing labels
    missing = [label for label in labels if label not in existing]
    if not missing:
        sys.exit(0)

    # Build helpful error with gh label create suggestions
    suggestions = "\n".join(f'  gh label create "{label}"' for label in missing)
    result = {
        "decision": "block",
        "reason": (
            f"BLOCKED: The following label(s) do not exist: {', '.join(missing)}\n"
            f"Create them first:\n{suggestions}\n\n"
            "See charter § GitHub Label Hygiene: verify labels exist before creating issues."
        ),
    }
    print(json.dumps(result))
    sys.exit(2)


if __name__ == "__main__":
    main()
