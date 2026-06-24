#!/usr/bin/env python3
"""Generate / staleness-check isnad-graph's structural ontology index (#1128).

This is the isnad-graph (consumer) side of the C×T2 distributed structural
ontology (parent meta noorinalabs-main#820, generator noorinalabs-main#855). It
does NOT contain the extraction logic — that lives, single-source-of-truth, in
the OWNED generator package ``ontology_gen`` in **noorinalabs-main**
(``.claude/lib/ontology_gen/``). This script is a thin consumer wrapper that:

* locates that generator (see :func:`locate_generator`),
* invokes it against this repo to (re)produce the two committed artifacts
  ``ontology/structural/{code-graph.json, llms.txt}``, and
* gates that those committed artifacts stay in sync with the source tree.

Why a sibling generator instead of a vendored copy
==================================================
The generator is deliberately NOT copied into this repo. A vendored copy would
fork: a fix to the extractor in noorinalabs-main would silently not reach the six
consuming repos, re-introducing the drift the owned-generator design exists to
remove (eval noorinalabs-main#854). Instead the generator is consumed from a
single source of truth:

* **CI** checks out noorinalabs-main as a sibling (resolving the ref to the
  matching wave branch with a ``main`` fallback — the established cross-repo
  pattern, cf. ``.github/workflows/schema-drift.yml`` /
  feedback_cross_repo_wave_ref_resolution, deploy#159) and points this script at
  it via ``--gen-lib`` / ``ONTOLOGY_GEN_LIB``.
* **Local dev** relies on the standard org layout (child repos cloned beneath
  ``noorinalabs-main/``); :func:`locate_generator` walks up to find the parent's
  ``.claude/lib/ontology_gen`` automatically. ``ONTOLOGY_GEN_LIB`` overrides for
  any non-standard checkout.

Tradeoff flagged for the P7W1 six-repo fan-out: the committed index is coupled to
the generator VERSION in noorinalabs-main. A generator change there can turn a
consumer's staleness gate red until the index is regenerated and re-committed —
expected for a drift gate, but the fan-out should sequence generator changes
ahead of a coordinated consumer-repo index refresh. See
``docs/devops/ontology-structural.md``.

Subcommands
===========
* ``emit``  — (re)generate the committed index in place.
* ``check`` — regenerate into a temp dir and fail (exit 1) if it differs from the
  committed index. This is what the CI job + the pre-commit hook run.
* ``register-merge-driver`` — register the union merge-driver in git config (the
  ``.gitattributes`` line is committed; the driver registration is per-clone
  local state, so ``make setup-hooks`` runs this). NOTE: the driver is invoked in
  PYTHON MODULE form (``python3 -m ontology_gen.merge_driver``), NOT as a bare
  script — ``merge_driver.py`` uses a package-relative import (``from .model``),
  so a plain ``python3 .../merge_driver.py`` invocation raises ImportError.
"""

from __future__ import annotations

import argparse
import difflib
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_NAME = "noorinalabs-isnad-graph"
OUT_REL = Path("ontology/structural")
ARTIFACTS = ("code-graph.json", "llms.txt")

# Env var a CI job (or a non-standard local checkout) uses to point at the
# directory that CONTAINS the ``ontology_gen`` package (i.e. the parent repo's
# ``.claude/lib``).
ENV_GEN_LIB = "ONTOLOGY_GEN_LIB"


def locate_generator(repo_root: Path, explicit: str | None) -> Path | None:
    """Return the dir to put on ``sys.path`` so ``import ontology_gen`` resolves.

    Returns ``None`` if the generator cannot be found — callers decide whether
    that is a hard error (``emit`` / CI ``check --require-generator``) or a
    graceful local skip (a developer who hasn't cloned noorinalabs-main, or whose
    parent checkout is on a branch that predates the generator).

    Resolution order:
      1. ``explicit`` (``--gen-lib`` flag) — used by CI's sibling checkout.
      2. ``$ONTOLOGY_GEN_LIB`` — same, via env.
      3. Walk up from ``repo_root``: for each ancestor, accept
         ``<ancestor>/.claude/lib`` or ``<ancestor>/noorinalabs-main/.claude/lib``
         when it contains the ``ontology_gen`` package. Covers the standard org
         layout (this repo cloned beneath ``noorinalabs-main/``).
    """
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.environ.get(ENV_GEN_LIB)
    if env:
        candidates.append(Path(env))
    for ancestor in [repo_root, *repo_root.parents]:
        candidates.append(ancestor / ".claude" / "lib")
        candidates.append(ancestor / "noorinalabs-main" / ".claude" / "lib")

    for cand in candidates:
        if (cand / "ontology_gen" / "__main__.py").is_file():
            return cand.resolve()
    return None


def _not_found_message() -> str:
    return (
        "could not locate the ontology_gen generator package.\n"
        "  The generator lives in noorinalabs-main at .claude/lib/ontology_gen/\n"
        "  (it is intentionally NOT vendored into this repo — single source of truth).\n"
        f"  Set {ENV_GEN_LIB}=<path-to>/noorinalabs-main/.claude/lib or pass\n"
        "  --gen-lib <path>. CI passes the sibling-checkout path automatically.\n"
    )


def _load_generate(gen_lib: Path):
    if str(gen_lib) not in sys.path:
        sys.path.insert(0, str(gen_lib))
    from ontology_gen.generate import generate  # noqa: PLC0415 (import after path setup)

    return generate


def _generate_into(gen_lib: Path, repo_root: Path, out_dir: Path) -> dict[str, int]:
    generate = _load_generate(gen_lib)
    return generate(repo_root, out_dir, REPO_NAME)


def cmd_emit(gen_lib: Path, repo_root: Path) -> int:
    out_dir = repo_root / OUT_REL
    counts = _generate_into(gen_lib, repo_root, out_dir)
    print(
        f"ontology_gen: {REPO_NAME} -> {OUT_REL} "
        f"(files={counts['files']} nodes={counts['nodes']} edges={counts['edges']})"
    )
    return 0


def cmd_check(gen_lib: Path | None, repo_root: Path, require_generator: bool) -> int:
    committed_dir = repo_root / OUT_REL
    missing = [a for a in ARTIFACTS if not (committed_dir / a).is_file()]
    if missing:
        # A real defect detectable WITHOUT the generator: the index is uncommitted.
        sys.stderr.write(
            f"error: committed structural index missing: {missing}\n"
            "  Generate it with: python3 scripts/structural_ontology.py emit\n"
        )
        return 1

    if gen_lib is None:
        # Authoritative enforcement is CI (which always sibling-checks-out the
        # generator and passes --require-generator). Locally, a missing generator
        # degrades to a warning so a developer without the parent repo can still
        # commit — it never silently passes in CI.
        if require_generator:
            sys.stderr.write("error: " + _not_found_message())
            return 2
        sys.stderr.write(
            "warning: " + _not_found_message() + "  Skipping local staleness check "
            "(CI enforces it authoritatively).\n"
        )
        return 0

    drifted = False
    with tempfile.TemporaryDirectory() as tmp:
        fresh_dir = Path(tmp)
        _generate_into(gen_lib, repo_root, fresh_dir)
        for artifact in ARTIFACTS:
            committed = (committed_dir / artifact).read_text(encoding="utf-8")
            fresh = (fresh_dir / artifact).read_text(encoding="utf-8")
            if committed == fresh:
                continue
            drifted = True
            sys.stderr.write(f"\nDRIFT: ontology/structural/{artifact} is stale vs source.\n")
            diff = difflib.unified_diff(
                committed.splitlines(keepends=True),
                fresh.splitlines(keepends=True),
                fromfile=f"committed/{artifact}",
                tofile=f"regenerated/{artifact}",
                n=1,
            )
            shown = 0
            for line in diff:
                sys.stderr.write(line if line.endswith("\n") else line + "\n")
                shown += 1
                if shown >= 60:
                    sys.stderr.write("  ... (diff truncated)\n")
                    break

    if drifted:
        sys.stderr.write(
            "\nThe committed structural ontology index is out of date with the source tree.\n"
            "Regenerate and commit it:\n"
            "  python3 scripts/structural_ontology.py emit\n"
            "  git add ontology/structural/\n"
        )
        return 1
    print("OK: structural ontology index is current with source.")
    return 0


def cmd_register_merge_driver(gen_lib: Path, repo_root: Path) -> int:
    import subprocess  # noqa: PLC0415 (only this subcommand shells out)

    # Module form is required: merge_driver.py uses a relative import, so a bare
    # ``python3 .../merge_driver.py`` raises ImportError.
    driver = f"PYTHONPATH={gen_lib} python3 -m ontology_gen.merge_driver %O %A %B %P"
    subprocess.run(
        ["git", "config", "merge.ontology-codegraph.driver", driver],
        cwd=repo_root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "merge.ontology-codegraph.name", "union merge for code-graph.json"],
        cwd=repo_root,
        check=True,
    )
    print(f"registered merge driver 'ontology-codegraph': {driver}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("emit", "check", "register-merge-driver"),
        help="emit: write the index; check: fail if stale; register-merge-driver: git config.",
    )
    parser.add_argument(
        "--gen-lib",
        default=None,
        help=(
            "Directory containing the ontology_gen package (parent repo's "
            f".claude/lib). Defaults to ${ENV_GEN_LIB} or auto-discovery."
        ),
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help="Repo root to index (default: this repo).",
    )
    parser.add_argument(
        "--require-generator",
        action="store_true",
        help=(
            "Treat a missing generator as a hard error (exit 2) instead of a "
            "graceful local skip. CI passes this so a check never false-passes."
        ),
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    gen_lib = locate_generator(repo_root, args.gen_lib)

    if args.command == "check":
        return cmd_check(gen_lib, repo_root, args.require_generator)

    # emit / register-merge-driver are explicit operator actions — the generator
    # must be present.
    if gen_lib is None:
        sys.stderr.write("error: " + _not_found_message())
        return 2
    if args.command == "emit":
        return cmd_emit(gen_lib, repo_root)
    return cmd_register_merge_driver(gen_lib, repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
