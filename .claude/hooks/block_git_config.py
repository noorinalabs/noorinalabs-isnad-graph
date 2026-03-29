#!/usr/bin/env python3
"""PreToolUse hook: Block git config write commands.

The charter mandates per-commit `-c` flags — never modify global or repo-level
git config. This hook blocks `git config` write commands while allowing reads
(--get, --get-all, --list, -l) which are needed by Makefile and other tooling.

Exit codes:
  0 — allow (not a git config command, or a read-only operation)
  2 — block (git config write detected)
"""

import json
import re
import sys

# Read-only git config flags/subcommands that should be allowed
_READ_ONLY_PATTERNS = re.compile(
    r"--get\b|--get-all\b|--get-regexp\b|--list\b|-l\b|--show-origin\b|--show-scope\b"
)


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    command = input_data.get("tool_input", {}).get("command", "")

    # Match `git config` as a standalone command
    if not re.search(r"\bgit\s+config\b", command):
        sys.exit(0)

    # Allow read-only operations
    if _READ_ONLY_PATTERNS.search(command):
        sys.exit(0)

    result = {
        "decision": "block",
        "reason": (
            "BLOCKED: `git config` writes are prohibited by the charter (§ Commit Identity). "
            "Never modify global or repo-level git config. "
            "Use per-commit `-c` flags instead:\n"
            '  git -c user.name="Name" -c user.email="email@example.com" commit -m "..."\n'
            "Read-only operations (--get, --list, -l) are allowed.\n"
            "See .claude/team/charter.md § Commit Identity for the full identity table."
        ),
    }
    print(json.dumps(result))
    sys.exit(2)


if __name__ == "__main__":
    main()
