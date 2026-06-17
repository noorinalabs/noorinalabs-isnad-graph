"""Emit and diff the canonical hadith-grade vocabulary for the frontend.

The grade vocabulary — the canonical token set and each token's human-readable
display label (``GRADE_LABELS``) — has a single source of truth in the backend
module ``src/utils/grades.py``. The frontend used to hand-maintain a second copy
of ``GRADE_LABELS`` in ``frontend/src/lib/grades.ts``; the two could silently
drift (ig#1054). This script makes the frontend *derive* the labels instead:

- ``emit``  — read ``GRADE_LABELS`` from ``src.utils.grades`` and write it as an
  ordered JSON map to ``frontend/src/lib/grade-vocab.generated.json`` (the
  ``--out`` default). ``frontend/src/lib/grades.ts`` imports that file, so the
  backend is the only place a grade label is defined.
- ``check`` — regenerate the JSON in memory and compare against the committed
  file, exiting non-zero on any drift. This is what the ``grade-vocab-drift`` CI
  step and the ``grade-vocab-drift`` pre-commit hook run to gate PRs.

Mirrors the emit/check shape of ``scripts/emit_ingest_schema.py`` and the
``gen:types`` + ``git diff --exit-code`` drift gate already used for the
user-service OpenAPI types in ``.github/workflows/ci.yml``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# scripts/ is a sibling of src/; make ``src`` importable when run directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.utils.grades import GRADE_LABELS, GRADE_TOKENS  # noqa: E402

_DEFAULT_OUT = _REPO_ROOT / "frontend" / "src" / "lib" / "grade-vocab.generated.json"


def _render() -> str:
    """Return the canonical grade-label JSON (insertion order preserved).

    Guards the backend invariant that every canonical token has a display label:
    ``GRADE_LABELS`` keys must equal the canonical token set so the frontend can
    never receive a vocabulary that is missing a label (or carries a stray one).
    """
    if set(GRADE_LABELS) != set(GRADE_TOKENS):
        missing = set(GRADE_TOKENS) - set(GRADE_LABELS)
        extra = set(GRADE_LABELS) - set(GRADE_TOKENS)
        raise SystemExit(
            "GRADE_LABELS is out of sync with the canonical token set "
            f"(missing labels: {sorted(missing)}; stray labels: {sorted(extra)}). "
            "Fix src/utils/grades.py before regenerating."
        )
    # Sort by display order (GRADE_LABELS insertion order) so the frontend facet
    # order is stable and reviewable; trailing newline keeps it diff-friendly.
    return json.dumps(dict(GRADE_LABELS), indent=2, ensure_ascii=False) + "\n"


def _emit(out: Path) -> None:
    out.write_text(_render(), encoding="utf-8")
    print(f"wrote {out.relative_to(_REPO_ROOT)} ({len(GRADE_LABELS)} grade labels)")


def _check(out: Path) -> int:
    expected = _render()
    if not out.exists():
        print(
            f"::error::{out.relative_to(_REPO_ROOT)} is missing — run "
            "`python scripts/emit_grade_vocab.py emit`",
            file=sys.stderr,
        )
        return 1
    actual = out.read_text(encoding="utf-8")
    if actual != expected:
        print(
            f"::error::{out.relative_to(_REPO_ROOT)} is out of sync with "
            "src/utils/grades.py GRADE_LABELS. Run "
            "`python scripts/emit_grade_vocab.py emit` and commit the result.",
            file=sys.stderr,
        )
        return 1
    print(f"{out.relative_to(_REPO_ROOT)} is in sync with src/utils/grades.py")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("emit", "check"):
        p = sub.add_parser(name)
        p.add_argument(
            "--out",
            type=Path,
            default=_DEFAULT_OUT,
            help="path to the generated JSON (default: the frontend grade-vocab.generated.json)",
        )
    args = parser.parse_args(argv)
    if args.cmd == "emit":
        _emit(args.out)
        return 0
    return _check(args.out)


if __name__ == "__main__":
    raise SystemExit(main())
