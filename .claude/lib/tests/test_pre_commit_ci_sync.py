"""Tests for pre_commit_ci_sync — the pre-commit <-> CI drift gate (#327).

Scoped to the cspell-kind classification that closes the spell-check blind spot
(noorinalabs-main#684): docs.yml's `Spellcheck (cspell)` job must register as the
`cspell` kind so the drift gate DEMANDS a `.pre-commit-config.yaml` mirror — an
un-classified spell gate produces ZERO drift signal, which is the exact silent
divergence the gate exists to prevent.

This repo's helper is the line-scanner classifier (not the parent's structural
parser), so these tests exercise it through the same public entry points the gate
uses: ``kinds_from_ci`` / ``kinds_from_precommit`` / ``compute_drift``.

Run:  python3 -m pytest .claude/lib/tests/test_pre_commit_ci_sync.py -q
  or  python3 -m unittest discover -s .claude/lib/tests
(this repo's main suite has ``testpaths = ["tests"]``, so it is invoked
explicitly, the same way the docs.yml sync gate runs the helper directly).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Helper lives at .claude/lib/pre_commit_ci_sync.py; this test is at
# .claude/lib/tests/test_*.py. parent.parent reaches the lib root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pre_commit_ci_sync import (  # noqa: E402
    check_repo,
    compute_drift,
    kinds_from_ci,
    kinds_from_precommit,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]


class CspellKindClassification(unittest.TestCase):
    """#684: a CI Spellcheck job must classify as the `cspell` kind on EITHER
    expression — the `streetsidesoftware/cspell-action` `uses:` ref, a bundled
    `cspell` CLI run, or the generic `spellcheck` word — and a pre-commit cspell
    hook must classify too, so a CI spell gate with no local mirror produces
    harmful drift instead of silence."""

    def test_cspell_action_uses_ref_classified(self) -> None:
        wf = """
jobs:
  spellcheck:
    name: Spellcheck (cspell)
    steps:
      - name: cspell
        uses: streetsidesoftware/cspell-action@de2a73e # v8.4.0
"""
        self.assertIn("cspell", kinds_from_ci(wf))

    def test_cspell_cli_run_step_classified(self) -> None:
        wf = """
jobs:
  spell:
    steps:
      - run: npx cspell --config .cspell.json "**/*.md"
"""
        self.assertIn("cspell", kinds_from_ci(wf))

    def test_generic_spellcheck_word_classified(self) -> None:
        # A repo that names the step/run with the generic word still registers.
        self.assertIn("cspell", kinds_from_ci("      - run: make spellcheck\n"))

    def test_precommit_cspell_hook_classified(self) -> None:
        cfg = """
repos:
  - repo: https://github.com/streetsidesoftware/cspell-cli
    rev: v8.4.0
    hooks:
      - id: cspell
        name: cspell
"""
        self.assertIn("cspell", kinds_from_precommit(cfg))

    def test_ci_cspell_without_precommit_is_harmful_drift(self) -> None:
        # The exact divergence #684 exists to catch: CI enforces cspell, the
        # pre-commit config does not mirror it.
        wf = """
jobs:
  spellcheck:
    steps:
      - uses: streetsidesoftware/cspell-action@de2a73e
"""
        cfg = """
repos:
  - repo: local
    hooks:
      - id: ruff
"""
        harmful, _ = compute_drift(kinds_from_precommit(cfg), kinds_from_ci(wf))
        self.assertIn("cspell", harmful)

    def test_ci_cspell_with_precommit_mirror_no_drift(self) -> None:
        wf = """
jobs:
  spellcheck:
    steps:
      - uses: streetsidesoftware/cspell-action@de2a73e
"""
        cfg = """
repos:
  - repo: https://github.com/streetsidesoftware/cspell-cli
    rev: v8.4.0
    hooks:
      - id: cspell
"""
        harmful, _ = compute_drift(kinds_from_precommit(cfg), kinds_from_ci(wf))
        self.assertNotIn("cspell", harmful)


class RealRepoHasNoCspellDrift(unittest.TestCase):
    """End-to-end against this repo's own files: docs.yml enforces cspell and
    .pre-commit-config.yaml now mirrors it, so the gate must see no cspell drift.
    This is the gate exactly as the `Pre-commit ⇄ CI sync-drift gate` job runs
    it — globbing ALL workflow files."""

    def test_repo_ci_enforces_cspell(self) -> None:
        wf_dir = _REPO_ROOT / ".github" / "workflows"
        ci_kinds: set[str] = set()
        for p in sorted(wf_dir.glob("*.y*ml")):
            if p.is_file():
                ci_kinds |= kinds_from_ci(p.read_text(encoding="utf-8"))
        self.assertIn("cspell", ci_kinds)

    def test_repo_precommit_mirrors_cspell(self) -> None:
        precommit = _REPO_ROOT / ".pre-commit-config.yaml"
        self.assertIn("cspell", kinds_from_precommit(precommit.read_text(encoding="utf-8")))

    def test_repo_has_no_cspell_drift(self) -> None:
        precommit = _REPO_ROOT / ".pre-commit-config.yaml"
        wf_dir = _REPO_ROOT / ".github" / "workflows"
        ci_paths = sorted(wf_dir.glob("*.y*ml"))
        self.assertTrue(ci_paths, "repo must have workflow files")
        harmful, _ = check_repo(precommit, ci_paths)
        self.assertNotIn(
            "cspell",
            harmful,
            f"cspell must be mirrored in pre-commit; harmful drift: {sorted(harmful)}",
        )


if __name__ == "__main__":
    unittest.main()
