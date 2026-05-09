#!/usr/bin/env python3
"""Backport: parser-fixture coverage for `block_git_config` (isnad-graph #867).

The hook source lives in the parent repo only (canonical-hook-paths migration,
issue #263). These fixtures import it from the parent and pin the same
input-language guarantees the parent tests assert, so a divergence between
parent hook behavior and what this child repo expects is caught at CI time.

Run: python3 -m pytest .claude/hooks/tests/test_block_git_config.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Walk up from this file to the noorinalabs-main parent and import the
# canonical hook from there. The child repo deliberately holds no copy of
# the hook source (charter `hooks.md § Hook Sync Across Child Repos`).
_HERE = Path(__file__).resolve().parent
_PARENT_HOOKS_DIR: Path | None = None
for _candidate in _HERE.parents:
    _maybe = _candidate.parent / "noorinalabs-main" / ".claude" / "hooks"
    if (_maybe / "block_git_config.py").is_file():
        _PARENT_HOOKS_DIR = _maybe
        break
if _PARENT_HOOKS_DIR is None:
    raise RuntimeError(
        "Could not locate noorinalabs-main/.claude/hooks/ from "
        f"{_HERE} — child-repo tests require the parent canonical "
        "hook source per charter `hooks.md § Hook Sync Across Child Repos`."
    )
sys.path.insert(0, str(_PARENT_HOOKS_DIR))

import block_git_config as hook  # noqa: E402


def _input(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


class PositiveMatchTests(unittest.TestCase):
    """Real `git config` writes MUST be blocked (issue #867 fixtures 1, 2, 8)."""

    def test_repo_level_user_name_write(self):
        """Fixture 1: `git config user.name "Alice"` — repo-level write blocked."""
        result = hook.check(_input('git config user.name "Alice"'))
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["decision"], "block")

    def test_global_user_email_write(self):
        """Fixture 2: `git config --global user.email ...` — global write blocked."""
        result = hook.check(_input('git config --global user.email "a@b.c"'))
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["decision"], "block")

    def test_chained_write_after_status(self):
        """Fixture 8: chained `git status && git config user.name x` — segment-walked."""
        result = hook.check(_input('git status && git config user.name "x"'))
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["decision"], "block")

    def test_dash_C_repo_write(self):
        """`git -C /repo config user.name` — global flag form, still a write."""
        result = hook.check(_input("git -C /repo config user.name foo"))
        self.assertIsNotNone(result)


class ReadOnlyAllowlistTests(unittest.TestCase):
    """`_READ_ONLY_PATTERNS` allowlist (issue #867 fixtures 3-6)."""

    def test_get_user_name(self):
        """Fixture 3: `git config --get user.name` — read-only, allow."""
        self.assertIsNone(hook.check(_input("git config --get user.name")))

    def test_list(self):
        """Fixture 4: `git config --list` — read-only, allow."""
        self.assertIsNone(hook.check(_input("git config --list")))

    def test_l_short(self):
        """Fixture 5: `git config -l` — short form of --list, allow."""
        self.assertIsNone(hook.check(_input("git config -l")))

    def test_show_origin(self):
        """Fixture 6: `git config --show-origin` — read-only, allow."""
        self.assertIsNone(hook.check(_input("git config --show-origin")))

    def test_get_all(self):
        """`git config --get-all user.email` — read-only, allow."""
        self.assertIsNone(hook.check(_input("git config --get-all user.email")))

    def test_get_regexp(self):
        """`git config --get-regexp ^user` — read-only, allow."""
        self.assertIsNone(hook.check(_input("git config --get-regexp ^user")))

    def test_show_scope(self):
        """`git config --show-scope` — read-only, allow."""
        self.assertIsNone(hook.check(_input("git config --show-scope")))

    def test_get_regexp_equals_form(self):
        """`--get-regexp=^user` — equals-form prefix of a read-only flag, allow."""
        self.assertIsNone(hook.check(_input("git config --get-regexp=^user")))


class FalsePositiveCandidateTests(unittest.TestCase):
    """Tokens that look like `git config` but aren't command-position invocations.

    Issue #867 fixture 7 calls these out as false-positive candidates that a
    naive `\\bgit\\s+config\\b` regex would match. The parent hook tokenizes
    via shlex and walks compound-command segments, so prose / argument values
    must NOT trigger.
    """

    def test_echo_argument_phrase(self):
        """Fixture 7: `echo "git config user.name x"` — prose in echo argument."""
        self.assertIsNone(hook.check(_input('echo "git config user.name x"')))

    def test_grep_argument_phrase(self):
        """`grep "git config" /tmp/foo` — phrase as grep pattern argument."""
        self.assertIsNone(hook.check(_input('grep "git config" /tmp/foo')))

    def test_per_commit_dash_c_user_name(self):
        """Per-commit `-c user.name=...` is the canonical bypass — MUST NOT block.

        This is the exact pattern the hook directs callers to via its block
        message. Blocking it would create a deadlock.
        """
        cmd = 'git -c user.name="Idris Yusuf" -c user.email="x@y.z" commit -m "msg"'
        self.assertIsNone(hook.check(_input(cmd)))

    def test_gh_issue_body_file_reference(self):
        """`gh issue create --body-file /tmp/x.md` — body file content not on cmdline."""
        cmd = "gh issue create --repo noorinalabs/noorinalabs-isnad-graph --body-file /tmp/body.md"
        self.assertIsNone(hook.check(_input(cmd)))

    def test_gh_issue_inline_body_phrase(self):
        """`gh issue create --body "...git config..."` — phrase in body argument."""
        cmd = 'gh issue create --body "the git config write block trips here"'
        self.assertIsNone(hook.check(_input(cmd)))

    def test_heredoc_body_mentions_phrase(self):
        """Heredoc body containing the literal phrase — stripped before tokenizing."""
        cmd = "cat > /tmp/x.md <<'EOF'\nWe block git config because of the charter rule.\nEOF"
        self.assertIsNone(hook.check(_input(cmd)))


class NonBashIgnoredTests(unittest.TestCase):
    """The hook only fires on Bash tool_name; other tools pass through."""

    def test_edit_tool_passthrough(self):
        """Edit tool with a `command` field — hook returns None (only fires on Bash)."""
        self.assertIsNone(
            hook.check(
                {
                    "tool_name": "Edit",
                    "tool_input": {"command": "git config user.name foo"},
                }
            )
        )

    def test_write_tool_passthrough(self):
        self.assertIsNone(
            hook.check(
                {
                    "tool_name": "Write",
                    "tool_input": {"file_path": "/tmp/x", "content": "git config user.name foo"},
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
