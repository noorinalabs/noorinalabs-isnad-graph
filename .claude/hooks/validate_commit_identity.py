#!/usr/bin/env python3
"""PreToolUse hook: Validate git commit identity flags.

Ensures every `git commit` command includes `-c user.name=` and `-c user.email=`
flags matching a roster member from the charter's Commit Identity table.

Exit codes:
  0 — allow (not a git commit, or identity is valid)
  2 — block (missing or invalid identity flags)
"""

import json
from pathlib import Path
import re
import sys

# Load roster from shared JSON file — single source of truth for all hooks
_ROSTER_PATH = Path(__file__).resolve().parent.parent / "team" / "roster.json"
try:
    ROSTER: dict[str, str] = json.loads(_ROSTER_PATH.read_text(encoding="utf-8"))
except (FileNotFoundError, json.JSONDecodeError):
    # Fallback: allow if roster file is missing (don't block all commits)
    ROSTER = {}


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    command = input_data.get("tool_input", {}).get("command", "")

    # Only match git commit commands (not git commit --amend checking, etc.)
    # We want any command that contains "git" followed by "commit"
    if not re.search(r"\bgit\b.*\bcommit\b", command):
        sys.exit(0)

    # Extract -c user.name="..." or -c user.name='...' or -c user.name=...
    name_match = re.search(r'-c\s+user\.name=["\']?([^"\']+)["\']?', command)
    email_match = re.search(r'-c\s+user\.email=["\']?([^"\']+)["\']?', command)

    if not name_match:
        result = {
            "decision": "block",
            "reason": (
                "BLOCKED: git commit missing `-c user.name=` flag. "
                "Charter § Commit Identity requires per-commit identity via -c flags. "
                "Example: git -c user.name=\"Kwame Asante\" -c user.email=\"parametrization+Kwame.Asante@gmail.com\" commit -m \"...\""
            ),
        }
        print(json.dumps(result))
        sys.exit(2)

    if not email_match:
        result = {
            "decision": "block",
            "reason": (
                "BLOCKED: git commit missing `-c user.email=` flag. "
                "Charter § Commit Identity requires per-commit identity via -c flags. "
                "Example: git -c user.name=\"Kwame Asante\" -c user.email=\"parametrization+Kwame.Asante@gmail.com\" commit -m \"...\""
            ),
        }
        print(json.dumps(result))
        sys.exit(2)

    name = name_match.group(1).strip()
    email = email_match.group(1).strip()

    # Validate against roster
    if name not in ROSTER:
        result = {
            "decision": "block",
            "reason": (
                f"BLOCKED: user.name=\"{name}\" is not a recognized roster member. "
                f"Valid names: {', '.join(sorted(ROSTER.keys()))}"
            ),
        }
        print(json.dumps(result))
        sys.exit(2)

    expected_email = ROSTER[name]
    if email != expected_email:
        result = {
            "decision": "block",
            "reason": (
                f"BLOCKED: user.email=\"{email}\" does not match roster for {name}. "
                f"Expected: {expected_email}"
            ),
        }
        print(json.dumps(result))
        sys.exit(2)

    # Identity is valid
    sys.exit(0)


if __name__ == "__main__":
    main()
