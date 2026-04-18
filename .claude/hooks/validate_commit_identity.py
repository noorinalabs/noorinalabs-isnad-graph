#!/usr/bin/env python3
"""PreToolUse hook: Validate git commit identity flags.

Fires on: Bash tool calls.
Matches: `git commit` invocations (including those with `-c` flags or after
    shell operators like `&&`, `||`, `;`, `|`). Also matches the pattern
    `cd <path> && git commit ...` to resolve cross-repo commits against the
    target repo's roster.
Does NOT match: `git config`, `git log`, `git show`, nor occurrences of the
    literal text "git commit" that appear inside heredoc bodies or inside
    single-/double-quoted strings (e.g., within a commit message).
Flag pass-through: N/A — this hook is advisory/blocking, it does not rewrite
    the command.

Roster resolution (parent+child merge):
  When the hook fires in a child repository (a repo whose working directory
  is nested under a parent that itself contains a `.claude/team/roster.json`),
  the hook loads BOTH rosters and treats the union as valid. On name
  collision with a differing email, the CHILD roster wins (per-repo override
  semantics). The parent roster path is inferred from the filesystem
  position of this hook file — never from an environment variable or a
  user-supplied path — so it cannot be spoofed by a crafted command.

Exit codes:
  0 — allow (not a git commit, or identity is valid)
  2 — block (missing or invalid identity flags)
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from annunaki_log import log_pretooluse_block
except ImportError:
    # Child repos may not have annunaki instrumentation installed yet.
    # Signature must match annunaki_log.log_pretooluse_block exactly — mypy
    # requires identical signatures across conditional function variants.
    def log_pretooluse_block(  # type: ignore[no-redef]
        hook_name: str, command: str, reason: str, tool_name: str = "Bash"
    ) -> None:
        return None


# Local roster path — this hook's repo's roster (either the parent org-level
# repo, or a child repo). Single source of truth for identities owned by
# THIS repo.
_LOCAL_ROSTER_PATH = Path(__file__).resolve().parent.parent / "team" / "roster.json"


def _load_roster(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _find_parent_roster_path(local_repo_root: Path) -> Path | None:
    """Locate the parent (org-level) roster, if this is a child repo.

    Walks up from `local_repo_root.parent` looking for a directory whose
    `.claude/team/roster.json` is distinct from the local one. Returns the
    first such path, or None if this IS the top-level repo.

    Security note: derived purely from the filesystem location of the hook
    file. Cannot be influenced by the Bash command being validated, env
    vars, or any external input.
    """
    try:
        local_roster = (local_repo_root / ".claude" / "team" / "roster.json").resolve()
    except OSError:
        return None

    current = local_repo_root.parent
    while True:
        candidate = current / ".claude" / "team" / "roster.json"
        if candidate.is_file():
            try:
                if candidate.resolve() != local_roster:
                    return candidate
            except OSError:
                pass
        if current.parent == current:
            return None
        current = current.parent


def _merge_rosters(parent: dict[str, str], child: dict[str, str]) -> dict[str, str]:
    """Union of parent+child rosters; child wins on name collision."""
    merged = dict(parent)
    merged.update(child)
    return merged


def _build_effective_roster(local_roster_path: Path) -> dict[str, str]:
    """Compute the effective roster for a given local-roster file.

    The local repo root is derived from the roster path:
      <local_repo_root>/.claude/team/roster.json
    i.e. three parents up from the roster file.
    """
    local_roster = _load_roster(local_roster_path)
    try:
        local_repo_root = local_roster_path.parents[2]
    except IndexError:
        return local_roster

    parent_roster_path = _find_parent_roster_path(local_repo_root)
    if parent_roster_path is None:
        return local_roster

    parent_roster = _load_roster(parent_roster_path)
    return _merge_rosters(parent_roster, local_roster)


# Effective roster at import time — merged parent+child if applicable.
ROSTER: dict[str, str] = _build_effective_roster(_LOCAL_ROSTER_PATH)


def _detect_target_roster(command: str) -> dict[str, str] | None:
    """Detect cross-repo commits and load the target repo's effective roster.

    When the command contains `cd /path/to/repo && git commit ...`, the
    commit targets a different repo. Load that repo's roster.json (plus its
    parent roster, if any) and return the merged result.

    Returns the target repo's effective (merged) roster dict, or None to use
    the local ROSTER.
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
    return _build_effective_roster(roster_path)


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
