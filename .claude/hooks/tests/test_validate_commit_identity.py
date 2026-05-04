#!/usr/bin/env python3
"""Tests for validate_commit_identity hook.

Covers:
- Parent+child roster merge (#819) — org-level coordinators in parent's
  roster.json are recognized for commits inside this child repo.
- Cross-repo `cd <path>` target detection — when a command cd's into a
  sibling repo, that target's merged roster is used.
- Strip-pass ordering invariants (#814) — heredoc bodies are stripped
  before quoted strings; mentions of `git commit` inside string literals
  do not trigger false positives, and quoted text containing heredoc-
  delimiter-like tokens does not break heredoc stripping.

Run: python3 -m pytest .claude/hooks/tests/test_validate_commit_identity.py -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_HOOKS_DIR = _HERE.parent
sys.path.insert(0, str(_HOOKS_DIR))

import validate_commit_identity as hook  # noqa: E402


def _git_init(path: Path) -> None:
    """Init a bare git repo at `path` by creating `.git` as a dir stub.

    The hook only checks `(path / ".git").exists()`. Creating `.git` as a
    directory satisfies the check deterministically without subprocesses.
    """
    (path / ".git").mkdir(parents=True, exist_ok=True)


def _write_roster(repo_path: Path, roster: dict[str, str]) -> None:
    team_dir = repo_path / ".claude" / "team"
    team_dir.mkdir(parents=True, exist_ok=True)
    (team_dir / "roster.json").write_text(json.dumps(roster), encoding="utf-8")


class LoadMergedRosterTests(unittest.TestCase):
    """Unit tests for `_load_merged_roster` — parent+child merge semantics."""

    def test_child_only_no_parent(self):
        """Parent roster missing → returns child roster unchanged."""
        with tempfile.TemporaryDirectory() as td:
            outer = Path(td)
            _git_init(outer)
            child = outer / "child"
            child.mkdir()
            _git_init(child)
            _write_roster(child, {"Alice": "alice@example.com"})

            merged = hook._load_merged_roster(child)
            self.assertEqual(merged, {"Alice": "alice@example.com"})

    def test_parent_not_a_git_repo(self):
        """Parent dir exists but is NOT a git repo → parent ignored."""
        with tempfile.TemporaryDirectory() as td:
            outer = Path(td)
            _write_roster(outer, {"ShouldNotAppear": "nope@example.com"})
            child = outer / "child"
            child.mkdir()
            _git_init(child)
            _write_roster(child, {"Alice": "alice@example.com"})

            merged = hook._load_merged_roster(child)
            self.assertEqual(merged, {"Alice": "alice@example.com"})
            self.assertNotIn("ShouldNotAppear", merged)

    def test_parent_is_git_repo_without_roster(self):
        """Parent is a git repo but has no `.claude/team/roster.json` → ignored."""
        with tempfile.TemporaryDirectory() as td:
            outer = Path(td)
            _git_init(outer)
            child = outer / "child"
            child.mkdir()
            _git_init(child)
            _write_roster(child, {"Alice": "alice@example.com"})

            merged = hook._load_merged_roster(child)
            self.assertEqual(merged, {"Alice": "alice@example.com"})

    def test_child_plus_parent_merge_union(self):
        """Parent + child with disjoint names → union of both."""
        with tempfile.TemporaryDirectory() as td:
            outer = Path(td)
            _git_init(outer)
            _write_roster(outer, {"Nadia": "nadia@example.com"})
            child = outer / "child"
            child.mkdir()
            _git_init(child)
            _write_roster(child, {"Alice": "alice@example.com"})

            merged = hook._load_merged_roster(child)
            self.assertEqual(
                merged,
                {
                    "Nadia": "nadia@example.com",
                    "Alice": "alice@example.com",
                },
            )

    def test_child_wins_on_name_collision(self):
        """Same name in both with different emails → child email wins."""
        with tempfile.TemporaryDirectory() as td:
            outer = Path(td)
            _git_init(outer)
            _write_roster(outer, {"Alice": "alice-parent@example.com"})
            child = outer / "child"
            child.mkdir()
            _git_init(child)
            _write_roster(child, {"Alice": "alice-child@example.com"})

            merged = hook._load_merged_roster(child)
            self.assertEqual(merged, {"Alice": "alice-child@example.com"})

    def test_walk_only_one_level_grandparent_ignored(self):
        """Grandparent has roster, parent does not → grandparent NOT loaded."""
        with tempfile.TemporaryDirectory() as td:
            grand = Path(td)
            _git_init(grand)
            _write_roster(grand, {"Grandparent": "gp@example.com"})
            parent = grand / "parent"
            parent.mkdir()
            child = parent / "child"
            child.mkdir()
            _git_init(child)
            _write_roster(child, {"Alice": "alice@example.com"})

            merged = hook._load_merged_roster(child)
            self.assertEqual(merged, {"Alice": "alice@example.com"})
            self.assertNotIn("Grandparent", merged)

    def test_malformed_parent_roster_does_not_block(self):
        """A broken parent roster.json must fail-open — child roster is returned."""
        with tempfile.TemporaryDirectory() as td:
            outer = Path(td)
            _git_init(outer)
            team_dir = outer / ".claude" / "team"
            team_dir.mkdir(parents=True)
            (team_dir / "roster.json").write_text("{ this is not valid json", encoding="utf-8")
            child = outer / "child"
            child.mkdir()
            _git_init(child)
            _write_roster(child, {"Alice": "alice@example.com"})

            merged = hook._load_merged_roster(child)
            self.assertEqual(merged, {"Alice": "alice@example.com"})


class DetectTargetRosterTests(unittest.TestCase):
    """Regression tests for `cd <path> && git commit` target-roster detection."""

    def test_cd_target_returns_merged_roster(self):
        """`cd <child> && git commit` loads child+parent merged roster."""
        with tempfile.TemporaryDirectory() as td:
            outer = Path(td)
            _git_init(outer)
            _write_roster(outer, {"Nadia": "nadia@example.com"})
            child = outer / "child"
            child.mkdir()
            _git_init(child)
            _write_roster(child, {"Alice": "alice@example.com"})

            command = f"cd {child} && git commit -m 'x'"
            detected = hook._detect_target_roster(command)
            self.assertIsNotNone(detected)
            assert detected is not None  # type-narrow
            self.assertEqual(
                detected,
                {
                    "Nadia": "nadia@example.com",
                    "Alice": "alice@example.com",
                },
            )

    def test_cd_target_with_no_roster_returns_none(self):
        """`cd <dir>` where dir has no roster → None (fall back to local)."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "nonroster"
            target.mkdir()
            command = f"cd {target} && git commit -m 'x'"
            self.assertIsNone(hook._detect_target_roster(command))

    def test_no_cd_returns_none(self):
        """Command without `cd` → None (use local ROSTER)."""
        self.assertIsNone(hook._detect_target_roster("git commit -m 'x'"))


class CheckIntegrationTests(unittest.TestCase):
    """Integration: end-to-end `check()` on parent+child merged roster."""

    def test_parent_only_name_accepted_in_child_commit(self):
        """Org-coordinator in parent roster is accepted via cd-target merge."""
        with tempfile.TemporaryDirectory() as td:
            outer = Path(td)
            _git_init(outer)
            _write_roster(outer, {"Nadia": "nadia@example.com"})
            child = outer / "child"
            child.mkdir()
            _git_init(child)
            _write_roster(child, {"Alice": "alice@example.com"})

            command = (
                f'cd {child} && git -c user.name="Nadia" '
                f'-c user.email="nadia@example.com" commit -m "x"'
            )
            result = hook.check({"tool_name": "Bash", "tool_input": {"command": command}})
            self.assertIsNone(result, f"expected allow, got block: {result}")

    def test_child_email_override_blocks_parent_email(self):
        """When child overrides a name's email, the parent email is rejected."""
        with tempfile.TemporaryDirectory() as td:
            outer = Path(td)
            _git_init(outer)
            _write_roster(outer, {"Alice": "alice-parent@example.com"})
            child = outer / "child"
            child.mkdir()
            _git_init(child)
            _write_roster(child, {"Alice": "alice-child@example.com"})

            command = (
                f'cd {child} && git -c user.name="Alice" '
                f'-c user.email="alice-parent@example.com" commit -m "x"'
            )
            result = hook.check({"tool_name": "Bash", "tool_input": {"command": command}})
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result.get("decision"), "block")

    def test_819_reproducer_org_coordinator_in_isnad_graph(self):
        """#819 reproducer: org TPM (parent-only) must commit in child without cd.

        Models the exact failure cited in #819: an org-level coordinator (e.g.
        Wanjiku Mwangi) defined ONLY in the parent repo's roster.json must be
        accepted by the child repo's hook when committing inside the child
        worktree (no `cd` prefix; cwd already inside child). This is the
        scenario the runtime sync from PR #841 fixed; the test pins it.
        """
        with tempfile.TemporaryDirectory() as td:
            outer = Path(td)
            _git_init(outer)
            _write_roster(
                outer,
                {
                    "Wanjiku Mwangi": "parametrization+Wanjiku.Mwangi@gmail.com",
                    "Nadia Khoury": "parametrization+Nadia.Khoury@gmail.com",
                },
            )
            child = outer / "noorinalabs-isnad-graph"
            child.mkdir()
            _git_init(child)
            _write_roster(child, {"Linh Pham": "parametrization+Linh.Pham@gmail.com"})

            merged = hook._load_merged_roster(child)
            self.assertIn("Wanjiku Mwangi", merged)
            self.assertIn("Nadia Khoury", merged)
            self.assertIn("Linh Pham", merged)


class StripOrderingTests(unittest.TestCase):
    """#814 ordering-invariant tests for `_strip_heredocs` / `_strip_quoted_strings`.

    The hook's `_is_git_commit_command` runs heredocs first, then quoted strings.
    These tests pin that order so a future re-ordering breaks CI rather than
    silently corrupting commit-identity validation in production.
    """

    def test_heredoc_body_with_git_commit_is_not_a_commit(self):
        """A `cat <<EOF ... git commit ... EOF` is not a real git commit."""
        cmd = (
            "cat <<'EOF'\n"
            "instructions: do not run git commit by hand\n"
            "EOF\n"
        )
        self.assertFalse(
            hook._is_git_commit_command(cmd),
            "heredoc body containing the literal phrase 'git commit' must not "
            "be parsed as a real git commit invocation",
        )

    def test_quoted_string_with_git_commit_is_not_a_commit(self):
        """`echo 'git commit'` is not a real git commit."""
        self.assertFalse(
            hook._is_git_commit_command("echo 'git commit -m x'"),
            "literal 'git commit' inside a single-quoted argument must not "
            "trigger the commit-detection regex",
        )

    def test_double_quoted_git_commit_is_not_a_commit(self):
        """`echo "git commit"` is not a real git commit."""
        self.assertFalse(
            hook._is_git_commit_command('echo "git commit -m x"'),
            "literal 'git commit' inside a double-quoted argument must not "
            "trigger the commit-detection regex",
        )

    def test_real_git_commit_detected(self):
        """A real git commit (no heredocs/quotes hiding it) is detected."""
        self.assertTrue(
            hook._is_git_commit_command(
                'git -c user.name="Alice" -c user.email="a@b.c" commit -m "x"'
            ),
        )

    def test_real_git_commit_after_shell_operator(self):
        """A real git commit after `&&` is detected."""
        self.assertTrue(
            hook._is_git_commit_command("cd /tmp && git commit -m 'x'"),
        )

    def test_heredoc_strip_must_run_before_quote_strip(self):
        """Heredoc delimiter quoting requires heredocs to be stripped first.

        `<<'EOF'` is a single-quoted heredoc delimiter. If `_strip_quoted_strings`
        ran first, the `'EOF'` segment would be replaced with `''`, leaving the
        heredoc body un-stripped and exposing inner `git commit` text to the
        detector. The current order (heredocs → quoted strings) handles this
        correctly. This test fails loudly if a future contributor swaps the
        order of strip passes in `_is_git_commit_command`.
        """
        cmd = (
            "cat <<'EOF'\n"
            "git commit -m 'this is inside a heredoc'\n"
            "EOF\n"
        )
        self.assertFalse(
            hook._is_git_commit_command(cmd),
            "ordering invariant violated: heredoc bodies whose delimiters are "
            "quoted (<<'EOF') leaked through to commit detection",
        )

    def test_heredoc_body_with_quoted_tokens_is_handled(self):
        """A heredoc body containing single-quoted tokens does not break stripping."""
        cmd = (
            "cat <<EOF\n"
            "narrator says 'git commit' but it is just text\n"
            "EOF\n"
        )
        self.assertFalse(
            hook._is_git_commit_command(cmd),
            "heredoc body with embedded quoted text leaked through detection",
        )

    def test_quoted_string_containing_eof_token_does_not_terminate_heredoc(self):
        """A quoted string with `EOF`-shaped text does not confuse the strippers.

        Pins that the absence of an actual heredoc operator (`<<`) means the
        `EOF` token in a quoted string is just data and does not interact with
        heredoc stripping.
        """
        cmd = "echo 'EOF marker discussion: just words'"
        self.assertFalse(
            hook._is_git_commit_command(cmd),
            "quoted string with 'EOF'-like tokens spuriously detected as commit",
        )

    def test_nested_heredoc_inside_double_quoted_argument(self):
        """A heredoc-shaped fragment inside a double-quoted string is not parsed.

        `bash -c "cat <<EOF ... EOF"` — the `<<EOF` lives inside quotes. The
        current strippers run heredocs first against the raw text (so an actual
        heredoc operator across newlines is matched), then quotes (so the
        in-quote content is blanked). Either way, the inner mention of
        `git commit` must not be detected as a real invocation.
        """
        cmd = 'bash -c "cat <<EOF\ngit commit -m x\nEOF"'
        self.assertFalse(
            hook._is_git_commit_command(cmd),
            "inner git commit inside a quoted bash -c heredoc leaked through",
        )


if __name__ == "__main__":
    unittest.main()
