"""Hadith grade normalization.

The graph stores grades as free-text scholar strings on the
``(Hadith)-[:GRADED_BY]->(Grading {grade})`` node, e.g. ``"Sahih - Authentic"``,
``"Sahih-Authentic"``, ``"Hasan Sahih"``, ``"Da'if in chain"``, ``"Sahih Maqtu'"``,
``"Munkar"``, ``"Shadh"`` or Arabic ``"صحيح الإسناد مقطوع"``.

These raw values are kept for display, but they are useless for filtering and for
the frontend colour mapping, which both need a small, canonical vocabulary. This
module maps the free-text grade to one of a fixed set of canonical tokens and
provides the matching Cypher predicate so the API can filter by a canonical token
against the un-normalized graph (the long-term home for a stored
``grade_normalized`` is the data layer — cf. da#153).
"""

from __future__ import annotations

from typing import Final

# Keyword groups: a raw grade belongs to a group if its lower-cased text contains
# any of the group's substrings. Transliterations + Arabic only — the English
# glosses ("authentic"/"good"/"weak") always co-occur with the transliteration in
# the source data, so listing them would only add false-positive risk.
_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "sahih": ("sahih", "صحيح"),
    "hasan": ("hasan", "حسن"),
    "daif": ("da'if", "da’if", "daif", "ضعيف"),
    "mawdu": ("mawdu", "maudu", "موضوع"),
    "munkar": ("munkar", "منكر"),
    "shadh": ("shadh", "شاذ"),
}

# Canonical token -> human-readable display label.
GRADE_LABELS: Final[dict[str, str]] = {
    "sahih": "Sahih",
    "hasan": "Hasan",
    "hasan_sahih": "Hasan Sahih",
    "daif": "Da'if",
    "mawdu": "Mawdu'",
    "munkar": "Munkar",
    "shadh": "Shadh",
}

# Per-canonical-token predicate spec mirroring normalize_grade's priority:
#   (required keyword groups [all must match], excluded groups [none may match]).
# Defects (mawdu/munkar/shadh) take precedence over soundness grades, and the
# combined "hasan sahih" grade is distinguished from plain sahih / hasan.
_PREDICATES: Final[dict[str, tuple[tuple[str, ...], tuple[str, ...]]]] = {
    "mawdu": (("mawdu",), ()),
    "munkar": (("munkar",), ("mawdu",)),
    "shadh": (("shadh",), ("mawdu", "munkar")),
    "hasan_sahih": (("hasan", "sahih"), ("mawdu", "munkar", "shadh")),
    "sahih": (("sahih",), ("mawdu", "munkar", "shadh", "hasan")),
    "hasan": (("hasan",), ("mawdu", "munkar", "shadh", "sahih")),
    "daif": (("daif",), ("mawdu", "munkar", "shadh", "sahih", "hasan")),
}

# Canonical tokens in the priority order normalize_grade applies them.
GRADE_TOKENS: Final[tuple[str, ...]] = tuple(_PREDICATES.keys())


def normalize_grade(raw: str | None) -> str | None:
    """Map a free-text grade to a canonical token, or ``None`` if unrecognized.

    Priority: defect grades (mawdu > munkar > shadh) override soundness grades;
    a grade carrying both hasan and sahih keywords becomes ``hasan_sahih``.
    """
    if not raw or not raw.strip():
        return None
    text = raw.lower()

    def has(group: str) -> bool:
        return any(kw in text for kw in _KEYWORDS[group])

    for token, (required, excluded) in _PREDICATES.items():
        if all(has(g) for g in required) and not any(has(g) for g in excluded):
            return token
    return None


def grade_filter_clause(
    token: str, target: str, param_prefix: str = "grkw"
) -> tuple[str, dict[str, list[str]]]:
    """Build a Cypher boolean predicate matching ``target`` against a canonical token.

    ``target`` is a Cypher expression evaluating to the raw grade string (e.g.
    ``coalesce(g.grade, h.grade_composite, h.grade)``). Returns the predicate text
    and the parameter map of keyword lists. The predicate mirrors
    :func:`normalize_grade` exactly, so filtering by ``token`` returns precisely the
    hadiths whose grade normalizes to ``token``. Unknown tokens yield ``"false"``.
    """
    spec = _PREDICATES.get(token)
    if spec is None:
        return "false", {}
    required, excluded = spec
    params: dict[str, list[str]] = {}
    lowered = f"toLower({target})"

    def group_clause(group: str) -> str:
        key = f"{param_prefix}_{group}"
        params[key] = list(_KEYWORDS[group])
        return f"any(kw IN ${key} WHERE {lowered} CONTAINS kw)"

    parts = [group_clause(g) for g in required]
    if excluded:
        neg = " OR ".join(group_clause(g) for g in excluded)
        parts.append(f"NOT ({neg})")
    return "(" + " AND ".join(parts) + ")", params
