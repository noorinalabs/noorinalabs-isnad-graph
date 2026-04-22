#!/usr/bin/env python3
"""Shared Annunaki error logging utility.

Called by PreToolUse hooks when they block a command, so that blocked
commands appear in the Annunaki error log alongside PostToolUse errors.

Usage in any blocking hook:
    from annunaki_log import log_pretooluse_block
    log_pretooluse_block(hook_name="validate_commit_identity", command=command, reason=reason)
"""

import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ERRORS_FILE = REPO_ROOT / ".claude" / "annunaki" / "errors.jsonl"


def log_pretooluse_block(
    hook_name: str, command: str, reason: str, tool_name: str = "Bash"
) -> None:
    """Append a PreToolUse block event to the Annunaki error log."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "pretooluse_block",
        "hook": hook_name,
        "tool_name": tool_name,
        "command": command[:500],
        "exit_code": None,
        "matched_patterns": [f"hook_block:{hook_name}"],
        "error_lines": [reason[:500]],
        "stderr_excerpt": "",
    }

    ERRORS_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(ERRORS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass  # Never fail the hook
