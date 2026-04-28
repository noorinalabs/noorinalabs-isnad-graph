#!/usr/bin/env python3
"""PreToolUse hook: Block `gh pr merge` if CI is not green.

Queries `gh pr view --json statusCheckRollup` and blocks merge when any
required check has failed, been cancelled, timed out, or requires action.
Pending checks block unless the user passes `--auto` (warn-but-allow).

Exit codes:
  0 — allow (not a merge command, --admin override, or all checks green)
  2 — block (failing or pending checks without --auto)
"""

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annunaki_log import log_pretooluse_block

# Conclusion values that unambiguously indicate a failed check.
_FAILURE_CONCLUSIONS = {
    "FAILURE",
    "CANCELLED",
    "TIMED_OUT",
    "ACTION_REQUIRED",
    "STARTUP_FAILURE",
}

# Status values that indicate the check has not finished yet.
_PENDING_STATUSES = {"QUEUED", "IN_PROGRESS", "WAITING", "PENDING", "REQUESTED"}

# Bucket values (GitHub check rollup) that map to pass/fail.
_FAIL_BUCKETS = {"fail"}
_PASS_BUCKETS = {"pass", "skipping"}


def is_merge_command(command: str) -> bool:
    """Check if the command is a gh pr merge invocation, including chained commands."""
    for segment in re.split(r"\s*(?:&&|\|\||\||;)\s*", command):
        stripped = segment.lstrip()
        while re.match(r"[A-Za-z_][A-Za-z0-9_]*=\S*\s+", stripped):
            stripped = re.sub(r"^[A-Za-z_][A-Za-z0-9_]*=\S*\s+", "", stripped)
        if re.match(r"gh\s+pr\s+merge\b", stripped):
            return True
    return False


def extract_pr_number(command: str) -> str | None:
    """Extract PR number from gh pr merge command."""
    match = re.search(r"\bgh\s+pr\s+merge\s+(\d+)", command)
    if match:
        return match.group(1)
    match = re.search(r"/pull/(\d+)", command)
    if match:
        return match.group(1)
    return None


def extract_repo_from_command(command: str) -> str | None:
    """Extract --repo value from gh pr merge command."""
    match = re.search(r"--repo\s+(\S+)", command)
    if match:
        return match.group(1)
    return None


def fetch_checks(pr_number: str | None, repo: str | None) -> list[dict] | None:
    """Fetch statusCheckRollup entries for the PR. Returns None on failure."""
    try:
        cmd = ["gh", "pr", "view"]
        if pr_number:
            cmd.append(pr_number)
        if repo:
            cmd.extend(["--repo", repo])
        cmd.extend(["--json", "statusCheckRollup"])
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        rollup = data.get("statusCheckRollup", [])
        if not isinstance(rollup, list):
            return None
        return rollup
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


def classify_check(check: dict) -> str:
    """Return 'fail', 'pending', or 'pass' for a single check entry."""
    bucket = (check.get("bucket") or "").lower()
    conclusion = (check.get("conclusion") or "").upper()
    status = (check.get("status") or check.get("state") or "").upper()

    if bucket in _FAIL_BUCKETS or conclusion in _FAILURE_CONCLUSIONS:
        return "fail"
    if status in _PENDING_STATUSES or conclusion == "":
        # Completed with no conclusion is treated as success; truly pending
        # checks have status != COMPLETED.
        if status == "COMPLETED":
            return "pass"
        return "pending"
    if bucket in _PASS_BUCKETS or conclusion in {"SUCCESS", "NEUTRAL", "SKIPPED"}:
        return "pass"
    return "pass"


def check_name(check: dict) -> str:
    """Best-effort display name for a check."""
    return check.get("name") or check.get("context") or check.get("workflowName") or "<unnamed>"


def check_url(check: dict) -> str:
    """Best-effort URL for a check."""
    return check.get("detailsUrl") or check.get("targetUrl") or ""


def format_check_list(checks: list[dict]) -> str:
    lines = []
    for c in checks:
        name = check_name(c)
        conclusion = (c.get("conclusion") or c.get("status") or "").lower() or "unknown"
        url = check_url(c)
        suffix = f" ({url})" if url else ""
        lines.append(f"  - {name} [{conclusion}]{suffix}")
    return "\n".join(lines)


def check(input_data: dict) -> dict | None:
    """Check PR CI status. Returns result dict if blocking, None if allowed."""
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        return None

    command = input_data.get("tool_input", {}).get("command", "")

    if not is_merge_command(command):
        return None

    if "--admin" in command:
        return None

    pr_number = extract_pr_number(command)
    repo = extract_repo_from_command(command)
    rollup = fetch_checks(pr_number, repo)

    pr_display = f"#{pr_number}" if pr_number else "(current branch)"

    if rollup is None:
        return {
            "decision": "allow",
            "systemMessage": (
                f"WARNING: Could not verify CI status for PR {pr_display}. "
                "Ensure all checks are green before merging."
            ),
        }

    if not rollup:
        # No checks at all — allow (nothing to gate on).
        return None

    failing: list[dict] = []
    pending: list[dict] = []
    for entry in rollup:
        verdict = classify_check(entry)
        if verdict == "fail":
            failing.append(entry)
        elif verdict == "pending":
            pending.append(entry)

    if failing:
        result = {
            "decision": "block",
            "reason": (
                f"BLOCKED: PR {pr_display} has {len(failing)} failing CI check(s). "
                "Charter § Pull Requests requires green CI before merge.\n"
                f"Failing checks:\n{format_check_list(failing)}\n\n"
                "Fix the failures and re-run, or pass `--admin` for emergency overrides only."
            ),
        }
        log_pretooluse_block("validate_pr_ci_status", command, result["reason"])
        return result

    if pending:
        if "--auto" in command:
            return {
                "decision": "allow",
                "systemMessage": (
                    f"WARNING: PR {pr_display} has {len(pending)} pending CI check(s); "
                    "`--auto` will let GitHub merge when they finish.\n"
                    f"{format_check_list(pending)}"
                ),
            }
        result = {
            "decision": "block",
            "reason": (
                f"BLOCKED: PR {pr_display} has {len(pending)} pending CI check(s). "
                "Wait for CI to finish, pass `--auto` to let GitHub merge on green, "
                "or pass `--admin` for emergency overrides.\n"
                f"Pending checks:\n{format_check_list(pending)}"
            ),
        }
        log_pretooluse_block("validate_pr_ci_status", command, result["reason"])
        return result

    return None


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    result = check(input_data)
    if result is None:
        sys.exit(0)
    print(json.dumps(result))
    if result.get("decision") == "block":
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
