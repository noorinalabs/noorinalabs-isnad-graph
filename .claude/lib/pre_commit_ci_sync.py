#!/usr/bin/env python3
"""Detect drift between a repo's pre-commit config and what its CI enforces.

Phase-3 end-state criterion #6 (noorinalabs-main#327) requires that local
pre-commit / pre-push hooks MIRROR the GitHub Actions checks, so a developer's
local commit fails fast instead of surfacing a lint/type/test error only after
a PR is opened. This module is the drift GATE: it parses both sides into a set
of canonical "check kinds" and reports any check CI enforces that the
pre-commit config does NOT run locally.

Drift direction that matters
============================
We gate on **CI-enforced-but-not-local** drift only. That is the harmful
direction: CI catches something the dev's machine doesn't, so the failure
appears at PR time (the friction #327 exists to remove). The reverse
(local runs something CI doesn't) is *stricter local* — not a regression, so
it is reported as informational, never a gate failure.

Canonical check kinds
=====================
Heterogeneous repos express the same check different ways (a `ruff` CI `run:`
step vs a `ruff` pre-commit `id:`). We normalize both sides to a small set of
kind tokens so they compare:

    ruff-lint, ruff-format, mypy, pytest, eslint, typescript, prettier,
    terraform-fmt, gitleaks, actionlint, astro-check, pip-audit, build

Unknown tools are ignored (neither side gates on a kind we can't classify),
which keeps the gate conservative — it never fails on something it doesn't
understand.

Input Language
==============
- A pre-commit config is parsed for `id:` values AND `entry:`/`name:` text.
- A CI workflow is parsed for `run:` shell lines AND `uses:` action refs.
Both are matched against per-kind keyword patterns.

Exit codes (CLI):
    0 — no harmful drift (every CI-enforced kind is mirrored in pre-commit)
    1 — harmful drift (a CI-enforced kind is missing from pre-commit)
    2 — usage / file-not-found error
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Each kind maps to the keyword patterns that identify it on EITHER side
# (pre-commit id/entry text or CI run/uses text). Patterns are substrings
# matched case-insensitively against the relevant lines.
_KIND_PATTERNS: dict[str, tuple[str, ...]] = {
    "ruff-format": ("ruff-format", "ruff format"),
    "ruff-lint": ("ruff check", "id: ruff", "- ruff"),
    "mypy": ("mypy",),
    "pytest": ("pytest",),
    "eslint": ("eslint",),
    "typescript": ("tsc", "typecheck", "type-check", "astro check"),
    "prettier": ("prettier",),
    "terraform-fmt": ("terraform fmt", "terraform_fmt", "id: terraform"),
    "gitleaks": ("gitleaks",),
    "actionlint": ("actionlint",),
    "pip-audit": ("pip-audit", "pip audit"),
    "build": ("build-and-validate", "build-and-test", "npm run build", "docker build"),
}

# `ruff-lint` is a substring of nothing problematic, but `ruff format` also
# contains `ruff`, so order the lint check to NOT fire on a format-only line.
# We handle that by classifying format first and removing matched spans.


def _classify_line(line: str) -> set[str]:
    """Return the set of canonical kinds a single text line implies."""
    low = line.lower()
    kinds: set[str] = set()
    # Format must be tested before the bare-ruff lint pattern so that a
    # `ruff format` line is not also counted as `ruff-lint`.
    if any(p in low for p in _KIND_PATTERNS["ruff-format"]):
        kinds.add("ruff-format")
    for kind, patterns in _KIND_PATTERNS.items():
        if kind == "ruff-format":
            continue
        if kind == "ruff-lint" and (
            # Only count ruff-lint when it is not purely the format line.
            ("ruff format" in low) and ("ruff check" not in low and "id: ruff" not in low)
        ):
            continue
        if any(p in low for p in patterns):
            kinds.add(kind)
    return kinds


def kinds_from_precommit(config_text: str) -> set[str]:
    """Canonical check-kinds a `.pre-commit-config.yaml` runs locally."""
    kinds: set[str] = set()
    for raw in config_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Only lines that name a hook matter: id:, entry:, name:, - repo refs.
        if re.match(r"^(-\s*)?(id|entry|name|repo):", line) or line.startswith("- "):
            kinds |= _classify_line(line)
    return kinds


def kinds_from_ci(workflow_text: str) -> set[str]:
    """Canonical check-kinds a CI workflow enforces."""
    kinds: set[str] = set()
    for raw in workflow_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # CI expresses checks as `run:` shell or `uses:` actions.
        if "run:" in line or line.startswith("- run:") or "uses:" in line or line.startswith("-"):
            kinds |= _classify_line(line)
    return kinds


def compute_drift(precommit_kinds: set[str], ci_kinds: set[str]) -> tuple[set[str], set[str]]:
    """Return (harmful_drift, stricter_local).

    harmful_drift  = CI enforces it, pre-commit does not (gate fails on these).
    stricter_local = pre-commit runs it, CI does not (informational only).
    """
    harmful = ci_kinds - precommit_kinds
    stricter = precommit_kinds - ci_kinds
    return harmful, stricter


def check_repo(precommit_path: Path, ci_paths: list[Path]) -> tuple[set[str], set[str]]:
    """Read the files and compute drift. Missing files contribute nothing."""
    pc_text = precommit_path.read_text(encoding="utf-8") if precommit_path.is_file() else ""
    ci_text = "\n".join(p.read_text(encoding="utf-8") for p in ci_paths if p.is_file())
    return compute_drift(kinds_from_precommit(pc_text), kinds_from_ci(ci_text))


def _default_ci_paths(repo_root: Path) -> list[Path]:
    wf_dir = repo_root / ".github" / "workflows"
    if not wf_dir.is_dir():
        return []
    return sorted(p for p in wf_dir.glob("*.y*ml"))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="Repo root to check (default: cwd).",
    )
    parser.add_argument(
        "--precommit",
        help="Path to .pre-commit-config.yaml (default: <repo_root>/.pre-commit-config.yaml).",
    )
    parser.add_argument(
        "--ci",
        action="append",
        help=(
            "Path to a CI workflow file (repeatable). "
            "Default: all <repo_root>/.github/workflows/*.yml."
        ),
    )
    args = parser.parse_args(argv[1:])

    repo_root = Path(args.repo_root).resolve()
    precommit_path = (
        Path(args.precommit) if args.precommit else repo_root / ".pre-commit-config.yaml"
    )
    ci_paths = [Path(p) for p in args.ci] if args.ci else _default_ci_paths(repo_root)

    if not precommit_path.is_file():
        print(
            f"ERROR: no pre-commit config at {precommit_path} — "
            "every repo must have one (criterion #327).",
            file=sys.stderr,
        )
        return 2

    harmful, stricter = check_repo(precommit_path, ci_paths)

    if stricter:
        print(f"INFO: pre-commit runs (CI does not): {sorted(stricter)} — stricter local, OK.")

    if harmful:
        print("DRIFT: CI enforces these checks but pre-commit does NOT run them locally:")
        for k in sorted(harmful):
            print(f"  - {k}")
        print(
            "\nAdd the missing check(s) to .pre-commit-config.yaml so local commits "
            "fail fast (criterion #327). Pin the same tool version CI uses."
        )
        return 1

    print("OK: pre-commit config mirrors all CI-enforced checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
