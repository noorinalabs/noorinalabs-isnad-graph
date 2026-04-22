#!/usr/bin/env python3
"""PreToolUse hook: Validate git commit identity flags.

Ensures every `git commit` command includes `-c user.name=` and `-c user.email=`
flags matching a roster member from the charter's Commit Identity table.

Parent+child roster merge (#112 part a):
  When the target repo (either the local repo or a `cd <path>` target) is a
  child of another git repo that itself has `.claude/team/roster.json`, the
  parent roster is loaded and merged with the child roster. Same-name entries
  in the child override the parent (child wins). Walk-up is limited to ONE
  level to avoid false positives in nested `code/` trees. This lets org-level
  coordinators commit in child repos without duplicating their entries into
  every child `roster.json`.

Exit codes:
  0 — allow (not a git commit, or identity is valid)
  2 — block (missing or invalid identity flags)
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from annunaki_log import log_pretooluse_block


def _read_roster(roster_path: Path) -> dict[str, str]:
    """Read a roster.json file, returning {} on any failure (fail-open)."""
    try:
        data = json.loads(roster_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_merged_roster(repo_path: Path) -> dict[str, str]:
    """Load `repo_path`'s roster, merged with its parent repo's roster if any.

    Parent detection (ONE level up only):
      1. `repo_path/..` must be a directory containing `.git` (i.e. a git repo).
      2. `repo_path/../.claude/team/roster.json` must exist.
    If both hold, the parent roster is loaded and merged under the child roster
    — child keys override parent keys, so a same-name entry in the child wins.
    Any OSError / malformed JSON at any step is swallowed; a broken parent
    roster must never block a child repo's valid commit.
    """
    child_path = repo_path / ".claude" / "team" / "roster.json"
    child_roster = _read_roster(child_path)

    try:
        parent_dir = repo_path.parent
        if (
            parent_dir != repo_path
            and (parent_dir / ".git").exists()
            and (parent_dir / ".claude" / "team" / "roster.json").is_file()
        ):
            parent_roster = _read_roster(parent_dir / ".claude" / "team" / "roster.json")
        else:
            parent_roster = {}
    except OSError:
        parent_roster = {}

    # Child wins on key collision.
    return {**parent_roster, **child_roster}


# Module-level roster for the repo hosting this hook. `_load_merged_roster`
# walks up one level; at this repo (noorinalabs-main) there is no parent repo
# with a roster, so this collapses to the local roster only.
ROSTER: dict[str, str] = _load_merged_roster(Path(__file__).resolve().parent.parent.parent)


def _detect_target_roster(command: str) -> dict[str, str] | None:
    """Detect cross-repo commits and load the target repo's merged roster.

    When the command contains `cd /path/to/repo && git commit ...`, the
    commit targets a different repo. Load that repo's roster.json (merged
    with its parent repo's roster if applicable — see `_load_merged_roster`)
    so we validate against the correct team, not the local one.

    Returns the target merged roster dict, or None to use the local ROSTER.
    """
    cd_match = re.search(r"cd\s+([^\s;&|]+)", command)
    if not cd_match:
        return None
    target_dir = Path(cd_match.group(1)).expanduser().resolve()
    if not target_dir.is_dir():
        return None
    roster_path = target_dir / ".claude" / "team" / "roster.json"
    if not roster_path.is_file():
        return None
    merged = _load_merged_roster(target_dir)
    return merged or None


def _strip_heredocs(text: str) -> str:
    """Remove heredoc bodies (<<'DELIM' ... DELIM and <<DELIM ... DELIM)."""
    return re.sub(
        r"<<-?\s*['\"]?(\w+)['\"]?.*?\n.*?\n\1\b",
        "",
        text,
        flags=re.DOTALL,
    )


def _strip_quoted_strings(text: str) -> str:
    """Remove content of single- and double-quoted strings."""
    # Remove single-quoted strings (no escaping inside single quotes in shell)
    text = re.sub(r"'[^']*'", "''", text)
    # Remove double-quoted strings (handle escaped quotes)
    text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
    return text


def _is_git_commit_command(command: str) -> bool:
    """Return True only if the command invokes `git ... commit` as a real command.

    Strips heredoc bodies and quoted strings first so that mentions of
    "git commit" inside string literals do not trigger a false positive.
    Then requires `git` to appear as a command — at the start of the
    (trimmed) command or after a shell operator (&&, ||, ;, |).
    """
    cleaned = _strip_heredocs(command)
    cleaned = _strip_quoted_strings(cleaned)

    # Match `git [options] commit` where commit is the subcommand.
    # Git options before the subcommand are: -c key=val, -C path, --flag, etc.
    # We skip those and check if the first non-option argument is "commit".
    return bool(
        re.search(
            r"(?:^|[;&|]\s*|&&\s*|\|\|\s*)\s*git\b"
            r"(?:\s+-c\s+\S+)*"  # skip -c key=val pairs
            r"(?:\s+-[A-Za-z]\s+\S+)*"  # skip other -X val options
            r"\s+commit(?:\s|$)",
            cleaned,
            re.MULTILINE,
        )
    )


def check(input_data: dict) -> dict | None:
    """Check commit identity. Returns result dict if blocking, None if allowed."""
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        return None

    command = input_data.get("tool_input", {}).get("command", "")

    if not _is_git_commit_command(command):
        return None

    # Cross-repo support: if the command `cd`s into another repo, load that
    # repo's roster instead of the local one. This allows the orchestration
    # layer (noorinalabs-main) to commit in child repos using their team members.
    roster = _detect_target_roster(command) or ROSTER

    name_match = re.search(r'-c\s+user\.name=["\']?([^"\']+)["\']?', command)
    email_match = re.search(r'-c\s+user\.email=["\']?([^"\']+)["\']?', command)

    if not name_match:
        result = {
            "decision": "block",
            "reason": (
                "BLOCKED: git commit missing `-c user.name=` flag. "
                "Charter § Commit Identity requires per-commit identity via -c flags. "
                'Example: git -c user.name="Kwame Asante" '
                '-c user.email="parametrization+Kwame.Asante@gmail.com" commit -m "..."'
            ),
        }
        log_pretooluse_block("validate_commit_identity", command, result["reason"])
        return result

    if not email_match:
        result = {
            "decision": "block",
            "reason": (
                "BLOCKED: git commit missing `-c user.email=` flag. "
                "Charter § Commit Identity requires per-commit identity via -c flags. "
                'Example: git -c user.name="Kwame Asante" '
                '-c user.email="parametrization+Kwame.Asante@gmail.com" commit -m "..."'
            ),
        }
        log_pretooluse_block("validate_commit_identity", command, result["reason"])
        return result

    name = name_match.group(1).strip()
    email = email_match.group(1).strip()

    if name not in roster:
        result = {
            "decision": "block",
            "reason": (
                f'BLOCKED: user.name="{name}" is not a recognized roster member. '
                f"Valid names: {', '.join(sorted(roster.keys()))}"
            ),
        }
        log_pretooluse_block("validate_commit_identity", command, result["reason"])
        return result

    expected_email = roster[name]
    if email != expected_email:
        result = {
            "decision": "block",
            "reason": (
                f'BLOCKED: user.email="{email}" does not match roster for {name}. '
                f"Expected: {expected_email}"
            ),
        }
        log_pretooluse_block("validate_commit_identity", command, result["reason"])
        return result

    return None


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    result = check(input_data)
    if result and result.get("decision") == "block":
        print(json.dumps(result))
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
