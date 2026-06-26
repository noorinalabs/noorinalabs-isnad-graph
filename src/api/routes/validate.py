"""Chronological-plausibility validation of isnad chains.

Promotes the soft teacher↔student temporal overlap heuristic — buried in
``src/resolve/disambiguate.py`` as a disambiguation filter — to a first-class,
read-only data-quality endpoint that flags ``TRANSMITTED_TO`` edges whose
narrators' active windows cannot overlap.

Owner decision (ig#1040): this is a **flag-for-review aid**, not an
auto-quarantine and not a public authenticity verdict. It doubles as a
regression signal for the in-flight isnad-segmentation fix (da#221): while
segmentation is incomplete many ``Narrator`` nodes are still partial chain
strings, so the scan is expected to surface a large number of false
impossibilities until that lands. Design accordingly — be conservative about
the ``impossible`` tier and lean on ``implausible`` whenever a verdict rests on
an estimated (assumed-lifespan) endpoint.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_neo4j
from src.api.models import (
    ChainValidationFlag,
    ChainValidationResponse,
    ChainValidationVerdict,
    NarratorWindow,
)
from src.utils.neo4j_client import Neo4jClient

router = APIRouter()

# Mirror of ``src.enrich.historical.DEFAULT_ASSUMED_LIFESPAN_AH``. Kept as a
# module constant (rather than importing the enrich layer into the API layer) so
# the API has no dependency on the enrichment pipeline; the value is a stable
# domain assumption, not a tuning knob.
DEFAULT_ASSUMED_LIFESPAN_AH = 80

# Hard cap on the number of candidate edges pulled from Neo4j in a single scan.
# The verdict logic runs in Python, so an unbounded scan would be both slow and
# memory-heavy on the full graph. When the cap is hit the response is marked
# ``truncated`` so callers know the counts are a partial view.
_MAX_SCAN = 5000


def _resolve_window(
    birth_year_ah: int | None,
    death_year_ah: int | None,
    assumed_lifespan_ah: int,
) -> tuple[tuple[int, int] | None, bool]:
    """Resolve a narrator's [start, end] active window in Hijri years.

    Returns ``(window, estimated)`` where ``window`` is ``None`` when neither
    year is known (the narrator cannot be placed in time) and ``estimated`` is
    True when an assumed-lifespan span filled a missing endpoint. Death-anchored:
    when only the death year is known (the common case for hadith narrators) the
    window is ``[death - lifespan, death]``; when only birth is known it is
    ``[birth, birth + lifespan]``.
    """
    if birth_year_ah is None and death_year_ah is None:
        return None, True
    if death_year_ah is None:
        assert birth_year_ah is not None
        return (birth_year_ah, birth_year_ah + assumed_lifespan_ah), True
    if birth_year_ah is None:
        return (death_year_ah - assumed_lifespan_ah, death_year_ah), True
    return (birth_year_ah, death_year_ah), False


def classify_edge(
    teacher_birth: int | None,
    teacher_death: int | None,
    student_birth: int | None,
    student_death: int | None,
    assumed_lifespan_ah: int = DEFAULT_ASSUMED_LIFESPAN_AH,
) -> tuple[ChainValidationVerdict | None, str, int | None]:
    """Classify a teacher→student ``TRANSMITTED_TO`` edge chronologically.

    Returns ``(verdict, reason, gap_years_ah)``. A ``verdict`` of ``None`` means
    the edge is *undated* — neither side could be placed in time, so nothing can
    be asserted (distinct from ``ok``, which is a positive "windows overlap").

    Tiering:

    * ``impossible`` — the two windows are disjoint and *both deciding endpoints
      are attested* (real years, no estimate). The gap is not an artefact of the
      assumed lifespan.
    * ``implausible`` — disjoint, but at least one deciding endpoint was an
      assumed-lifespan estimate, so the gap could be an artefact of missing data.
    * ``ok`` — the windows overlap (transmission is chronologically feasible).
    """
    tw, _t_est = _resolve_window(teacher_birth, teacher_death, assumed_lifespan_ah)
    sw, _s_est = _resolve_window(student_birth, student_death, assumed_lifespan_ah)
    if tw is None or sw is None:
        return None, "insufficient_dates", None

    (t_start, t_end) = tw
    (s_start, s_end) = sw

    # Overlap test: closed intervals overlap when each starts no later than the
    # other ends.
    if t_start <= s_end and s_start <= t_end:
        return "ok", "windows_overlap", None

    if t_end < s_start:
        # Teacher's window ends before the student's begins — the normal-direction
        # gap (teacher long dead before student was active). The deciding
        # endpoints are the teacher's end (death) and the student's start (birth).
        gap = s_start - t_end
        attested = teacher_death is not None and student_birth is not None
        reason = "teacher_predates_student"
    else:
        # Student's window ends before the teacher's begins — student older than
        # teacher. Deciding endpoints: student's end (death) and teacher's start
        # (birth).
        gap = t_start - s_end
        attested = student_death is not None and teacher_birth is not None
        reason = "student_predates_teacher"

    verdict: ChainValidationVerdict = "impossible" if attested else "implausible"
    return verdict, reason, gap


def _window_model(row: dict[str, Any], prefix: str, assumed_lifespan_ah: int) -> NarratorWindow:
    """Build a NarratorWindow from a prefixed Cypher result row."""
    birth = row.get(f"{prefix}_birth")
    death = row.get(f"{prefix}_death")
    window, estimated = _resolve_window(birth, death, assumed_lifespan_ah)
    start = window[0] if window else None
    end = window[1] if window else None
    return NarratorWindow(
        narrator_id=row[f"{prefix}_id"],
        name_ar=row.get(f"{prefix}_name_ar"),
        name_en=row.get(f"{prefix}_name_en"),
        birth_year_ah=birth,
        death_year_ah=death,
        window_start_ah=start,
        window_end_ah=end,
        estimated=estimated,
    )


@router.get("/validate/chains", response_model=ChainValidationResponse)
def validate_chains(
    verdict: ChainValidationVerdict | None = Query(
        None,
        description=(
            "Filter returned flags to a single verdict tier. When omitted, only "
            "the flagged tiers (impossible + implausible) are returned, "
            "impossible first."
        ),
    ),
    hadith_id: str | None = Query(
        None,
        description="Restrict the scan to the isnad of a single hadith (per-chain validation).",
    ),
    limit: int = Query(100, ge=1, le=500, description="Max flags to return."),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> ChainValidationResponse:
    """Flag chronologically impossible/implausible ``TRANSMITTED_TO`` edges.

    For each teacher→student edge whose narrators carry at least one Hijri
    date, resolve both active windows and verdict the edge (impossible /
    implausible / ok). ``summary`` reports per-verdict counts across *every*
    edge scanned (a regression signal as segmentation lands); ``flags`` returns
    the requested slice, capped by ``limit``.
    """
    assumed_lifespan_ah = DEFAULT_ASSUMED_LIFESPAN_AH

    # Pull candidate edges: teacher→student TRANSMITTED_TO where at least one of
    # the two narrators carries a date. (An edge where neither side has any date
    # is genuinely unjudgeable and is counted as ``undated``; we still need the
    # rows where exactly one side is dated to resolve an estimated window.)
    rows: list[dict[str, Any]] = neo4j.execute_read(
        """
        MATCH (teacher:Narrator)-[t:TRANSMITTED_TO]->(student:Narrator)
        WHERE ($hadith_id IS NULL OR t.hadith_id = $hadith_id)
          AND (teacher.birth_year_ah IS NOT NULL OR teacher.death_year_ah IS NOT NULL
               OR student.birth_year_ah IS NOT NULL OR student.death_year_ah IS NOT NULL)
        RETURN teacher.id AS teacher_id,
               teacher.name_ar AS teacher_name_ar, teacher.name_en AS teacher_name_en,
               teacher.birth_year_ah AS teacher_birth, teacher.death_year_ah AS teacher_death,
               student.id AS student_id,
               student.name_ar AS student_name_ar, student.name_en AS student_name_en,
               student.birth_year_ah AS student_birth, student.death_year_ah AS student_death,
               t.hadith_id AS hadith_id, t.position_in_chain AS position
        LIMIT $scan_limit
        """,
        {"hadith_id": hadith_id, "scan_limit": _MAX_SCAN + 1},
    )

    truncated = len(rows) > _MAX_SCAN
    rows = rows[:_MAX_SCAN]

    summary: dict[str, int] = {"impossible": 0, "implausible": 0, "ok": 0}
    undated = 0
    scanned = 0
    flagged: list[ChainValidationFlag] = []

    for r in rows:
        edge_verdict, reason, gap = classify_edge(
            r.get("teacher_birth"),
            r.get("teacher_death"),
            r.get("student_birth"),
            r.get("student_death"),
            assumed_lifespan_ah,
        )
        if edge_verdict is None:
            undated += 1
            continue
        scanned += 1
        summary[edge_verdict] += 1

        # Selection: explicit verdict filter, else the flagged tiers only.
        if verdict is not None:
            if edge_verdict != verdict:
                continue
        elif edge_verdict == "ok":
            continue

        flagged.append(
            ChainValidationFlag(
                verdict=edge_verdict,
                reason=reason,
                hadith_id=r.get("hadith_id"),
                position_in_chain=r.get("position"),
                teacher=_window_model(r, "teacher", assumed_lifespan_ah),
                student=_window_model(r, "student", assumed_lifespan_ah),
                gap_years_ah=gap,
            )
        )

    # Surface the strongest signals first: impossible before implausible before
    # ok, then widest gap, deterministically tie-broken by hadith id.
    _order = {"impossible": 0, "implausible": 1, "ok": 2}
    flagged.sort(key=lambda f: (_order[f.verdict], -(f.gap_years_ah or 0), f.hadith_id or ""))

    return ChainValidationResponse(
        flags=flagged[:limit],
        summary=summary,
        scanned=scanned,
        undated=undated,
        assumed_lifespan_ah=assumed_lifespan_ah,
        truncated=truncated,
    )
