"""Tests for hadith grade normalization (ig#1048).

Uses the production-shaped free-text grade strings actually present in the graph
(`Sahih - Authentic`, `Hasan Sahih`, `Da'if in chain`, Arabic `صحيح الإسناد مقطوع`,
…) rather than the toy canonical tokens that older fixtures pre-populated.
"""

from __future__ import annotations

import pytest

from src.utils.grades import (
    GRADE_TOKENS,
    grade_filter_clause,
    normalize_grade,
)

# (raw free-text grade, expected canonical token) — drawn from the stg distribution
# cited in the issue plus the apostrophe/Arabic variants.
PRODUCTION_GRADES: list[tuple[str, str]] = [
    ("Sahih - Authentic", "sahih"),
    ("Sahih-Authentic", "sahih"),
    ("Sahih", "sahih"),
    ("Sahih Maqtu'", "sahih"),
    ("صحيح الإسناد مقطوع", "sahih"),
    ("Hasan - Good", "hasan"),
    ("Hasan", "hasan"),
    ("Hasan Sahih", "hasan_sahih"),
    ("Daif - Weak", "daif"),
    ("Da'if", "daif"),
    ("Da'if in chain", "daif"),
    ("ضعيف", "daif"),
    ("Mawdu' - Fabricated", "mawdu"),
    ("Maudu", "mawdu"),
    ("Munkar", "munkar"),
    ("Shadh", "shadh"),
]


@pytest.mark.parametrize(("raw", "expected"), PRODUCTION_GRADES)
def test_normalize_grade_production_values(raw: str, expected: str) -> None:
    assert normalize_grade(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "no-grade-here", "unknown classification"])
def test_normalize_grade_unrecognized_returns_none(raw: str | None) -> None:
    assert normalize_grade(raw) is None


def test_defect_grades_take_precedence_over_soundness() -> None:
    # A string mentioning both a defect and a soundness keyword resolves to the defect.
    assert normalize_grade("Sahih but Munkar") == "munkar"
    assert normalize_grade("Mawdu' though attributed Sahih") == "mawdu"


def test_hasan_sahih_distinct_from_sahih_and_hasan() -> None:
    assert normalize_grade("Hasan Sahih") == "hasan_sahih"
    assert normalize_grade("Sahih") != "hasan_sahih"
    assert normalize_grade("Hasan") != "hasan_sahih"


def test_grade_filter_clause_unknown_token_is_false() -> None:
    clause, params = grade_filter_clause("not-a-grade", "g.grade")
    assert clause == "false"
    assert params == {}


def test_grade_filter_clause_emits_parameterized_predicate() -> None:
    clause, params = grade_filter_clause("sahih", "g.grade")
    assert "toLower(g.grade)" in clause
    # sahih excludes hasan (so "Hasan Sahih" is not caught by the sahih filter).
    assert "NOT" in clause
    # Keyword lists are passed as params (no string interpolation of values).
    assert any("sahih" in kws for kws in params.values())
    assert any("hasan" in kws for kws in params.values())


def _python_eval_clause(clause: str, params: dict[str, list[str]], raw: str) -> bool:
    """Evaluate the generated Cypher predicate in Python to assert it mirrors
    normalize_grade. The clause is built from a tiny, fixed Cypher subset:
    ``any(kw IN $KEY WHERE toLower(g.grade) CONTAINS kw)`` groups joined by AND
    with an optional ``NOT ( ... OR ... )``. Each group is replaced by its boolean
    value (computed from params) so only True/False/and/or/not/parens remain."""
    import re

    lowered = raw.lower()

    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        return str(any(kw in lowered for kw in params[key]))

    skeleton = re.sub(r"any\(kw IN \$(\w+) WHERE toLower\(g\.grade\) CONTAINS kw\)", repl, clause)
    skeleton = skeleton.replace("NOT (", "not (").replace(" AND ", " and ").replace(" OR ", " or ")
    return bool(eval(skeleton))  # noqa: S307 - skeleton is only booleans + operators


@pytest.mark.parametrize(("raw", "expected"), PRODUCTION_GRADES)
def test_filter_clause_matches_normalize_for_its_token(raw: str, expected: str) -> None:
    """The filter for token T must match exactly the raws that normalize to T."""
    for token in GRADE_TOKENS:
        clause, params = grade_filter_clause(token, "g.grade")
        matched = _python_eval_clause(clause, params, raw)
        assert matched == (token == expected), (
            f"token={token!r} raw={raw!r}: clause matched={matched}, normalize={expected!r}"
        )
