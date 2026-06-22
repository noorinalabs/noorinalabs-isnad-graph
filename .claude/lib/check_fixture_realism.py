#!/usr/bin/env python3
"""Lint Arabic-text fixtures for production-realism (vocalization + عن particle).

Deterministic conversion of `.claude/team/charter/pull-requests.md § Text-
Processing / NER / Graph Fixtures Must Use Production-Realistic Input`
(noorinalabs-main#735, charter-prose-inventory worklist item #1 / epic #726).
This is the "lint / review-lens" the section's *Enforcement opportunity*
sub-section names as the optional half of #671: a cheap static signal that an
Arabic fixture is a toy rather than a real upstream sample.

The fixture-masks-bug class recurred 5+ times — most damningly *inside its own
fix* (da#146 / PR #151 replaced an un-voweled toy blob with a Bukhari-h1 fixture
that contained no عن, masking the over-segmentation later surfaced as da#155; the
P5W5 thaqalayn parser shipped a schema-assumed fixture that hid 0% extracted
Arabic, da#175). A fixture that is *greener than real data* is masking a bug.

What this gate flags
====================
For every file it is given, the codepoints are scanned. A file with NO Arabic
letters is **not** an Arabic-text fixture and is skipped (passes — this lens only
judges Arabic fixtures). A file that DOES contain Arabic letters is flagged when:

  (a) it contains NO Arabic vocalization diacritic — none in the harakat range
      U+064B–U+0652 (ً tanwīn-fatḥ … ْ sukūn). Real corpus text is voweled;
      a fixture stripped of diacritics exercises a code path the production
      corpus never takes.
  (b) it lacks the high-frequency transmission particle عن (ʿan, U+0639 U+0646)
      anywhere — the substring a naive segmenter over-splits; omitting it lets an
      over-segmentation bug pass. (The section scopes this to isnad strings; the
      `files:`/discovery wiring chooses which paths are fixtures, and the check
      applies the floor to any Arabic-bearing fixture it is handed.)

The عن search runs over a diacritic-stripped copy of the text, NOT the raw bytes.
In real voweled corpus text the particle is written عَنْ — a fatḥa sits *between*
the ʿayn and the nūn — so a naive bare-`عن` substring search would FAIL on the
exact voweled fixtures criterion (a) demands. Stripping the harakat first
(عَنْ → عن) is what lets a production-realistic voweled chain satisfy both checks
at once (without it the two criteria would be mutually unsatisfiable).

Either condition alone flags the file; the diagnostic names which one(s) failed.

CLI
===
    python3 .claude/lib/check_fixture_realism.py <fixture> [<fixture> ...]

Exit codes:
    0 — every Arabic-text fixture carries vocalization AND the عن particle
        (non-Arabic files are skipped)
    1 — at least one Arabic-text fixture is un-voweled or lacks عن
    2 — usage / file-not-found error

Reusable template (same CLI/exit-code shape as
`.claude/lib/pre_commit_ci_sync.py`) so it wires identically into pre-commit and
CI. The parent repo `noorinalabs-main` ships no Arabic fixtures itself; pointing
this at each child's text-processing/NER/graph fixtures is a #735 follow-up.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The transmission particle عن (ʿan): U+0639 (ʿayn) U+0646 (nūn). Substring-
# searched verbatim, exactly as the charter rule specifies.
_AN_PARTICLE = "عن"  # عن

# Arabic vocalization diacritics — the harakat the rule names as `ً–ْ`:
# U+064B (tanwīn fatḥ) … U+0652 (sukūn), inclusive.
_DIACRITIC_START = 0x064B
_DIACRITIC_END = 0x0652

# Arabic consonantal letters (hamza U+0621 … yāʾ U+064A). Presence of any of
# these is what makes a file an "Arabic-text fixture" worth judging — distinct
# from the diacritics (which sit just above this range) and from digits/marks.
_LETTER_START = 0x0621
_LETTER_END = 0x064A

# Tatweel / kashida (U+0640) is an elongation glyph, not a letter or a vowel; it
# is stripped alongside the harakat so it cannot split the عن particle either.
_TATWEEL = 0x0640


def has_arabic_letters(text: str) -> bool:
    """True if the text contains at least one Arabic consonantal letter."""
    return any(_LETTER_START <= ord(ch) <= _LETTER_END for ch in text)


def has_vocalization(text: str) -> bool:
    """True if the text contains at least one harakat diacritic (U+064B–U+0652)."""
    return any(_DIACRITIC_START <= ord(ch) <= _DIACRITIC_END for ch in text)


def strip_diacritics(text: str) -> str:
    """Remove harakat (U+064B–U+0652) and tatweel so عَنْ collapses to عن."""
    return "".join(
        ch
        for ch in text
        if not (_DIACRITIC_START <= ord(ch) <= _DIACRITIC_END) and ord(ch) != _TATWEEL
    )


def has_an_particle(text: str) -> bool:
    """True if عن appears once diacritics/tatweel are stripped (عَنْ → عن)."""
    return _AN_PARTICLE in strip_diacritics(text)


def check_fixture_text(path: str, text: str) -> list[str]:
    """Return violation strings for one fixture (empty list = clean or skipped)."""
    if not has_arabic_letters(text):
        return []  # not an Arabic-text fixture — this lens does not judge it
    reasons: list[str] = []
    if not has_vocalization(text):
        reasons.append("no vocalization diacritics (none in U+064B–U+0652 ً–ْ)")
    if not has_an_particle(text):
        reasons.append("missing transmission particle عن")
    if not reasons:
        return []
    return [f"{path}: Arabic-text fixture is not production-realistic — {'; '.join(reasons)}"]


def check_file(path: Path) -> list[str]:
    return check_fixture_text(str(path), path.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    paths = argv[1:]
    if not paths:
        print(
            "usage: check_fixture_realism.py <fixture> [<fixture> ...]",
            file=sys.stderr,
        )
        return 2

    all_violations: list[str] = []
    for p in paths:
        path = Path(p)
        if not path.is_file():
            print(f"ERROR: not a file: {p}", file=sys.stderr)
            return 2
        all_violations.extend(check_file(path))

    if all_violations:
        print("Fixture-realism violations (pull-requests.md § Production-Realistic Input, #735):")
        for v in all_violations:
            print(f"  {v}")
        print(
            "\nArabic-text fixtures must be lifted from a real upstream sample: voweled "
            "(diacritics in U+064B–U+0652) and carrying the عن transmission particle. "
            "A fixture greener than real data masks the next bug in that path."
        )
        return 1

    print("OK: all Arabic-text fixtures carry vocalization and the عن particle.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
