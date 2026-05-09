#!/usr/bin/env python3
"""Tests for the parent's validate_labels hook, runnable from this child repo.

Backports the parent (`noorinalabs-main`) parser-fixture coverage for the
`validate_labels.py` Bash PreToolUse hook into this repo so that fixtures
exercise the parser when the repo is checked out standalone (e.g. CI run
from inside `noorinalabs-isnad-graph` without the parent clone alongside).

Why this file exists in a child repo:
    Per `noorinalabs-main/.claude/team/charter/hooks.md` § Hook Sync Across
    Child Repos, child repos do NOT keep local copies of shared hook
    `.py` source — the parent is the single source of truth. This test
    therefore imports the parent's `validate_labels.py` from a sibling
    `noorinalabs-main/.claude/hooks/` directory. If that directory is not
    discoverable from the test file's location (e.g. the repo was cloned
    in isolation without the parent), the suite is skipped with a clear
    explanatory message rather than failing with an ImportError.

Coverage (matches noorinalabs/noorinalabs-isnad-graph#869 and the parent
charter rule at hooks.md § Parser-Fixture Coverage Requirements):

    1. Single label, double-quoted    -- ExtractLabelsTests
    2. Comma-separated in one flag    -- ExtractLabelsTests
    3. Multiple separate label flags  -- ExtractLabelsTests
    4. Short form -l                  -- ExtractLabelsTests
    5. Equals form --label=foo        -- ExtractLabelsTests
    6. No label flags present         -- GateMatchingTests / CheckEndToEndTests
    7. NEGATIVE: gh issue list        -- GateMatchingTests (gate must NOT fire)
    8. NEGATIVE: gh pr create         -- GateMatchingTests
    9. NEGATIVE: --add-label/--remove-label (not real gh-issue-create flags;
       parser must NOT extract values)         -- UnknownFlagTests
   10. Label absent from existing set         -- CheckEndToEndTests (block)
   11. Label present in existing set          -- CheckEndToEndTests (allow)
   12. Network failure path (existing=set())  -- CheckEndToEndTests (warn-allow)
   13. Body-leak negative (Bug 2 #113)        -- NegativeMatchLabelsTests

Run:
    python3 -m pytest .claude/hooks/tests/test_validate_labels.py -v
or:
    python3 .claude/hooks/tests/test_validate_labels.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


def _locate_parent_hooks_dir() -> Path | None:
    """Find `noorinalabs-main/.claude/hooks/` from this file's location.

    Search order:
      1. Sibling-of-this-repo layout: <code-root>/noorinalabs-main/.claude/hooks
         (the canonical layout — child repos sit alongside the parent under
         a shared parent dir). Walk upward from this file looking for a
         `noorinalabs-main` directory that contains the hook file.
      2. Same-tree layout: parent of this repo IS noorinalabs-main (rare;
         used only for development worktrees inside the parent).

    Returns the hooks directory Path if found, else None.
    """
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        candidate = ancestor / "noorinalabs-main" / ".claude" / "hooks" / "validate_labels.py"
        if candidate.is_file():
            return candidate.parent
        if ancestor.name == "noorinalabs-main":
            local = ancestor / ".claude" / "hooks" / "validate_labels.py"
            if local.is_file():
                return local.parent
    return None


_PARENT_HOOKS_DIR = _locate_parent_hooks_dir()

if _PARENT_HOOKS_DIR is not None:
    sys.path.insert(0, str(_PARENT_HOOKS_DIR))
    import validate_labels as hook  # noqa: E402
else:
    hook = None  # type: ignore[assignment]


@unittest.skipIf(
    hook is None,
    f"parent validate_labels.py not discoverable from {Path(__file__).resolve()} — "
    "this child repo is checked out without a sibling noorinalabs-main clone. "
    "Run from the parent layout, or clone noorinalabs-main alongside this repo.",
)
class ExtractLabelsTests(unittest.TestCase):
    """Positive regression tests — labels appearing on the actual flag."""

    def test_long_flag_quoted(self):
        self.assertEqual(
            hook.extract_labels('gh issue create --label "bug"'),
            ["bug"],
        )

    def test_long_flag_unquoted(self):
        self.assertEqual(
            hook.extract_labels("gh issue create --label bug"),
            ["bug"],
        )

    def test_short_flag(self):
        self.assertEqual(
            hook.extract_labels('gh issue create -l "tech-debt"'),
            ["tech-debt"],
        )

    def test_equals_form(self):
        self.assertEqual(
            hook.extract_labels("gh issue create --label=bug"),
            ["bug"],
        )

    def test_short_equals_is_not_supported(self):
        """`-l=value` is NOT a recognized form; gh treats `-l` and value as
        separate tokens. The parser only handles `--label=value` (long-eq).
        Documents the parser's intentional asymmetry."""
        self.assertEqual(
            hook.extract_labels("gh issue create -l=bug"),
            [],
        )

    def test_multiple_long_flags(self):
        self.assertEqual(
            hook.extract_labels('gh issue create --label "bug" --label "tech-debt"'),
            ["bug", "tech-debt"],
        )

    def test_comma_separated_in_one_flag(self):
        self.assertEqual(
            hook.extract_labels('gh issue create --label "bug,tech-debt,p3-wave-8"'),
            ["bug", "tech-debt", "p3-wave-8"],
        )

    def test_comma_separated_with_whitespace_around_commas(self):
        """gh allows users to type `--label "a, b, c"`; whitespace inside
        the comma split must be stripped so labels match exactly."""
        self.assertEqual(
            hook.extract_labels('gh issue create --label "bug , tech-debt"'),
            ["bug", "tech-debt"],
        )

    def test_mixed_short_and_long(self):
        self.assertEqual(
            hook.extract_labels('gh issue create -l bug --label "tech-debt"'),
            ["bug", "tech-debt"],
        )


@unittest.skipIf(hook is None, "parent validate_labels.py not discoverable")
class NegativeMatchLabelsTests(unittest.TestCase):
    """NEGATIVE-MATCH coverage for Bug 2 (#113) — extraction false positives.

    The hook MUST NOT extract labels from text that appears inside the value
    of another flag (e.g. --body, --title).
    """

    def test_body_containing_example_label_flag_is_ignored(self):
        cmd = (
            'gh issue create --title "real title" '
            '--body "Example: gh issue create --label fake-label-xyz" '
            "--label real-label"
        )
        labels = hook.extract_labels(cmd)
        self.assertIn("real-label", labels)
        self.assertNotIn("fake-label-xyz", labels)

    def test_body_with_short_flag_variant_is_ignored(self):
        cmd = 'gh issue create --body "see: gh issue create -l phantom" -l real'
        labels = hook.extract_labels(cmd)
        self.assertIn("real", labels)
        self.assertNotIn("phantom", labels)

    def test_title_with_label_flag_text_is_ignored(self):
        cmd = 'gh issue create --title "use --label flag correctly" --label documentation'
        self.assertEqual(hook.extract_labels(cmd), ["documentation"])

    def test_no_label_flag_returns_empty(self):
        self.assertEqual(
            hook.extract_labels('gh issue create --title "x" --body "y"'),
            [],
        )


@unittest.skipIf(hook is None, "parent validate_labels.py not discoverable")
class UnknownFlagTests(unittest.TestCase):
    """`--add-label` / `--remove-label` are NOT `gh issue create` flags;
    they belong to `gh issue edit`. The parser only knows `--label`/`-l`,
    so values following these unknown flags must NOT be extracted as labels.

    This is negative-space coverage requested explicitly in the W8 brief
    for issue #869 — guards against a future parser broadening that would
    silently start matching edit-style flags on `create` commands.
    """

    def test_add_label_long_flag_value_not_extracted(self):
        self.assertEqual(
            hook.extract_labels("gh issue create --add-label tech-debt"),
            [],
        )

    def test_remove_label_long_flag_value_not_extracted(self):
        self.assertEqual(
            hook.extract_labels("gh issue create --remove-label tech-debt"),
            [],
        )

    def test_add_label_alongside_real_label_extracts_only_real(self):
        """Mixed unknown + known: only `--label` value reaches output."""
        self.assertEqual(
            hook.extract_labels("gh issue create --add-label nope --label bug"),
            ["bug"],
        )


@unittest.skipIf(hook is None, "parent validate_labels.py not discoverable")
class GateMatchingTests(unittest.TestCase):
    """The `check()` gate fires ONLY on gh issue create."""

    @staticmethod
    def _input(command: str) -> dict:
        return {"tool_name": "Bash", "tool_input": {"command": command}}

    def test_gh_issue_list_is_ignored(self):
        self.assertIsNone(hook.check(self._input("gh issue list --label bug")))

    def test_gh_issue_view_is_ignored(self):
        self.assertIsNone(hook.check(self._input("gh issue view 1 --label bug")))

    def test_gh_issue_edit_is_ignored(self):
        """`gh issue edit --add-label` is the legitimate edit-flow; gate must
        not fire for it (the create-only gate plus unknown-flag-not-extracted
        together guarantee no false-positive on edit commands)."""
        self.assertIsNone(hook.check(self._input("gh issue edit 869 --add-label tech-debt")))

    def test_gh_pr_create_is_ignored(self):
        self.assertIsNone(hook.check(self._input("gh pr create --label bug")))

    def test_gh_label_create_is_ignored(self):
        self.assertIsNone(hook.check(self._input("gh label create my-label")))

    def test_non_bash_tool_is_ignored(self):
        self.assertIsNone(
            hook.check(
                {
                    "tool_name": "Edit",
                    "tool_input": {"command": "gh issue create --label bug"},
                }
            )
        )

    def test_command_without_label_flag_is_allowed(self):
        self.assertIsNone(hook.check(self._input('gh issue create --title "x" --body "y"')))


@unittest.skipIf(hook is None, "parent validate_labels.py not discoverable")
class CheckEndToEndTests(unittest.TestCase):
    """End-to-end `check()` with `get_existing_labels` mocked."""

    @staticmethod
    def _input(command: str) -> dict:
        return {"tool_name": "Bash", "tool_input": {"command": command}}

    def test_existing_label_passes(self):
        with mock.patch.object(hook, "get_existing_labels", return_value={"bug"}):
            result = hook.check(self._input("gh issue create --label bug"))
        self.assertIsNone(result)

    def test_missing_label_blocks(self):
        with mock.patch.object(hook, "get_existing_labels", return_value={"bug"}):
            result = hook.check(self._input("gh issue create --label does-not-exist"))
        self.assertIsNotNone(result)
        self.assertEqual(result["decision"], "block")
        self.assertIn("does-not-exist", result["reason"])

    def test_repo_is_forwarded_to_get_existing_labels(self):
        with mock.patch.object(
            hook, "get_existing_labels", return_value={"frontend", "bug"}
        ) as mocked:
            result = hook.check(
                self._input(
                    "gh issue create --repo noorinalabs/noorinalabs-isnad-graph "
                    '--title "t" --body "b" --label frontend'
                )
            )
        self.assertIsNone(result)
        mocked.assert_called_once_with(repo="noorinalabs/noorinalabs-isnad-graph")

    def test_body_containing_fake_label_does_not_block(self):
        with mock.patch.object(hook, "get_existing_labels", return_value={"bug"}):
            result = hook.check(
                self._input('gh issue create --body "example: --label fake" --label bug')
            )
        self.assertIsNone(result, f"unexpected block: {result}")

    def test_label_fetch_failure_warns_not_blocks(self):
        """Network/permission failure path: get_existing_labels returns an
        empty set (its documented failure mode). The hook must warn-allow,
        not block, so a transient gh outage doesn't gridlock issue creation."""
        with mock.patch.object(hook, "get_existing_labels", return_value=set()):
            result = hook.check(self._input("gh issue create --label any"))
        self.assertIsNotNone(result)
        self.assertEqual(result["decision"], "allow")
        self.assertIn("WARNING", result.get("systemMessage", ""))

    def test_no_labels_to_validate_skips_fetch(self):
        with mock.patch.object(hook, "get_existing_labels", return_value={"bug"}) as mocked:
            result = hook.check(self._input('gh issue create --title "t" --body "b"'))
        self.assertIsNone(result)
        mocked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
