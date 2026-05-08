#!/usr/bin/env python3
"""PreToolUse hook: Auto-set ENVIRONMENT=test before pytest/make test.

Ensures ENVIRONMENT=test is present in the environment for any pytest or
`make test` command. If not already set, blocks with a corrected command
that prepends ENVIRONMENT=test.

Input Language
==============

Fires on:
    PreToolUse Bash

Matches (blocks if ENVIRONMENT=test missing):
    Any Bash command whose token stream, after stripping leading
    `VAR=value` environment assignments, contains a real test-runner
    invocation detected by the regexes `\\bpytest\\b` or `\\bmake\\s+test\\b`.
    Typical matched forms:
        pytest tests/
        uv run pytest
        python -m pytest
        make test
        DEBUG=1 pytest tests/            (env prefix preserved; still matches)

Does NOT match (short-circuit skips — #114 fix):
    1. Command whose effective argv[0] is `gh` — `gh` is a GitHub API
       client, never a test runner. `ENVIRONMENT=test gh pr comment ...`
       is nonsensical. Skip even if pytest/make-test text appears inside
       the command (almost always inside --body / --title content).
    2. Command containing a `--body` or `--body-file` flag — structured
       body content almost always contains user-supplied text that may
       mention pytest or `make test` without invoking them. This skip is
       intentionally broad: a non-gh tool like
       `some-tool --body "$(cat pytest.txt)"` is also skipped. The cost
       of a rare false negative on an exotic non-gh tool is lower than
       the cost of blocking every review / issue / comment that
       references pytest.

Both short-circuits run BEFORE the pytest/make-test regex check.

Detection order:
    1. Strip leading `VAR=value` tokens from the command.
    2. If the next token is `gh`, ALLOW (return None).
    3. If the command contains `--body` or `--body-file`, ALLOW.
    4. If `\\bpytest\\b` or `\\bmake\\s+test\\b` matches, require
       `\\bENVIRONMENT=test\\b` somewhere in the command; else BLOCK.

Exit codes:
    0 — allow (not a Bash tool, or skip condition met, or already has
        ENVIRONMENT=test)
    2 — block (real test command missing ENVIRONMENT=test)

Enforcement artifact for: noorinalabs/noorinalabs-main#114
Synced from parent: P3W7 Pattern G fix (isnad-graph local copy was missing skip conditions)
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annunaki_log import log_pretooluse_block  # noqa: E402

# Matches a leading `VAR=value` token (simple unquoted value).
_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=\S*\s+")

# `--body` or `--body-file` as a standalone flag. The trailing lookahead
# prevents matching `--body-foo` but still matches both `--body x`,
# `--body=x`, and `--body-file path`.
_BODY_FLAG = re.compile(r"(?<![\w-])--body(?:-file)?(?=[\s=]|$)")


def _strip_leading_env(command: str) -> str:
    """Remove leading `VAR=value ` assignments, return the remainder."""
    while True:
        m = _ENV_ASSIGN.match(command)
        if not m:
            return command
        command = command[m.end() :]


def _is_gh_invocation(command: str) -> bool:
    """True if the effective argv[0] (after env assignments) is `gh`."""
    stripped = _strip_leading_env(command).lstrip()
    if not stripped:
        return False
    token = stripped.split(None, 1)[0]
    return token == "gh"


def _has_body_flag(command: str) -> bool:
    """True if the command contains a --body or --body-file flag."""
    return bool(_BODY_FLAG.search(command))


def check(input_data: dict) -> dict | None:
    """Check for ENVIRONMENT=test on test commands.

    Returns result dict if blocking, None if allowed.
    """
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        return None

    command = input_data.get("tool_input", {}).get("command", "")

    # Short-circuit 1: gh subcommands are never test runners.
    if _is_gh_invocation(command):
        return None

    # Short-circuit 2: --body/--body-file flag implies structured content.
    if _has_body_flag(command):
        return None

    is_test_cmd = bool(re.search(r"\bpytest\b", command) or re.search(r"\bmake\s+test\b", command))
    if not is_test_cmd:
        return None

    if re.search(r"\bENVIRONMENT=test\b", command):
        return None

    return {
        "decision": "block",
        "reason": (
            "ENVIRONMENT=test is required for test commands but was not found in "
            "the command. Please prepend ENVIRONMENT=test to the command:\n"
            f"  ENVIRONMENT=test {command}"
        ),
    }


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    result = check(input_data)
    if result and result.get("decision") == "block":
        print(json.dumps(result))
        command = input_data.get("tool_input", {}).get("command", "")
        log_pretooluse_block(
            "auto_set_env_test",
            command,
            result["reason"],
            tool_name="Bash",
        )
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
