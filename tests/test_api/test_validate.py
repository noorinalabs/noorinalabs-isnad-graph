"""Tests for GET /validate/chains chronological-plausibility validation.

Pure-classifier units run fully offline; endpoint tests use the mocked-Neo4j
``client`` fixture (see ``conftest.py``), so the suite stays offline-green.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.api.routes.validate import (
    DEFAULT_ASSUMED_LIFESPAN_AH,
    _resolve_window,
    classify_edge,
)

from .routes import VALIDATE

# --- Pure unit tests: window resolution -------------------------------------


def test_resolve_window_both_known_is_attested() -> None:
    window, estimated = _resolve_window(50, 100, DEFAULT_ASSUMED_LIFESPAN_AH)
    assert window == (50, 100)
    assert estimated is False


def test_resolve_window_death_only_is_death_anchored_estimate() -> None:
    window, estimated = _resolve_window(None, 100, 80)
    assert window == (20, 100)
    assert estimated is True


def test_resolve_window_birth_only_estimate() -> None:
    window, estimated = _resolve_window(50, None, 80)
    assert window == (50, 130)
    assert estimated is True


def test_resolve_window_no_dates_is_none() -> None:
    window, estimated = _resolve_window(None, None, 80)
    assert window is None
    assert estimated is True


# --- Pure unit tests: edge classification -----------------------------------


def test_classify_overlapping_windows_is_ok() -> None:
    # teacher [70,150] (death 150) overlaps student [120,200] (death 200)
    verdict, reason, gap = classify_edge(None, 150, None, 200)
    assert verdict == "ok"
    assert reason == "windows_overlap"
    assert gap is None


def test_classify_attested_gap_is_impossible() -> None:
    # teacher [50,100], student [200,260] — both deciding endpoints attested.
    verdict, reason, gap = classify_edge(50, 100, 200, 260)
    assert verdict == "impossible"
    assert reason == "teacher_predates_student"
    assert gap == 100


def test_classify_estimated_gap_is_implausible() -> None:
    # teacher death-only [20,100], student death-only [220,300]: the student
    # start (220) is an assumed-lifespan estimate, so the gap is not provable.
    verdict, reason, gap = classify_edge(None, 100, None, 300)
    assert verdict == "implausible"
    assert reason == "teacher_predates_student"
    assert gap == 120


def test_classify_student_predates_teacher_is_impossible_when_attested() -> None:
    # teacher [200,260], student [50,100] — student fully before teacher.
    verdict, reason, gap = classify_edge(200, 260, 50, 100)
    assert verdict == "impossible"
    assert reason == "student_predates_teacher"
    assert gap == 100


def test_classify_no_dates_is_undated() -> None:
    verdict, reason, gap = classify_edge(None, None, None, None)
    assert verdict is None
    assert reason == "insufficient_dates"
    assert gap is None


# --- Endpoint tests ----------------------------------------------------------


def _row(
    *,
    t_birth: int | None,
    t_death: int | None,
    s_birth: int | None,
    s_death: int | None,
    hadith_id: str = "h1",
    position: int = 1,
) -> dict[str, Any]:
    return {
        "teacher_id": "n-teacher",
        "teacher_name_ar": "معلم",
        "teacher_name_en": "Teacher",
        "teacher_birth": t_birth,
        "teacher_death": t_death,
        "student_id": "n-student",
        "student_name_ar": "تلميذ",
        "student_name_en": "Student",
        "student_birth": s_birth,
        "student_death": s_death,
        "hadith_id": hadith_id,
        "position": position,
    }


def test_validate_chains_empty(client: TestClient) -> None:
    resp = client.get(VALIDATE + "/chains")
    assert resp.status_code == 200
    body = resp.json()
    assert body["flags"] == []
    assert body["summary"] == {"impossible": 0, "implausible": 0, "ok": 0}
    assert body["scanned"] == 0
    assert body["undated"] == 0
    assert body["assumed_lifespan_ah"] == DEFAULT_ASSUMED_LIFESPAN_AH
    assert body["truncated"] is False


def test_validate_chains_default_returns_flagged_only(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    mock_neo4j.execute_read.return_value = [
        _row(t_birth=50, t_death=100, s_birth=200, s_death=260, hadith_id="imp"),  # impossible
        _row(t_birth=None, t_death=100, s_birth=None, s_death=300, hadith_id="impl"),  # implausible
        _row(t_birth=None, t_death=150, s_birth=None, s_death=200, hadith_id="okk"),  # ok
        _row(t_birth=None, t_death=None, s_birth=None, s_death=None, hadith_id="und"),  # undated
    ]
    resp = client.get(VALIDATE + "/chains")
    assert resp.status_code == 200
    body = resp.json()

    # summary counts every judged edge; undated excluded from scanned.
    assert body["summary"] == {"impossible": 1, "implausible": 1, "ok": 1}
    assert body["scanned"] == 3
    assert body["undated"] == 1

    # Default omits ``ok``; impossible sorts first.
    verdicts = [f["verdict"] for f in body["flags"]]
    assert verdicts == ["impossible", "implausible"]
    first = body["flags"][0]
    assert first["hadith_id"] == "imp"
    assert first["gap_years_ah"] == 100
    assert first["teacher"]["estimated"] is False
    assert first["teacher"]["window_start_ah"] == 50
    assert first["student"]["window_end_ah"] == 260


def test_validate_chains_verdict_filter_ok(client: TestClient, mock_neo4j: MagicMock) -> None:
    mock_neo4j.execute_read.return_value = [
        _row(t_birth=50, t_death=100, s_birth=200, s_death=260),  # impossible
        _row(t_birth=None, t_death=150, s_birth=None, s_death=200, hadith_id="okk"),  # ok
    ]
    resp = client.get(VALIDATE + "/chains", params={"verdict": "ok"})
    assert resp.status_code == 200
    body = resp.json()
    assert [f["verdict"] for f in body["flags"]] == ["ok"]
    assert body["flags"][0]["reason"] == "windows_overlap"


def test_validate_chains_hadith_id_passed_to_query(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    mock_neo4j.execute_read.return_value = []
    resp = client.get(VALIDATE + "/chains", params={"hadith_id": "sunnah:bukhari:1"})
    assert resp.status_code == 200
    params = mock_neo4j.execute_read.call_args[0][1]
    assert params["hadith_id"] == "sunnah:bukhari:1"


def test_validate_chains_limit_caps_flags(client: TestClient, mock_neo4j: MagicMock) -> None:
    mock_neo4j.execute_read.return_value = [
        _row(t_birth=50, t_death=100, s_birth=200, s_death=260, hadith_id=f"h{i}") for i in range(5)
    ]
    resp = client.get(VALIDATE + "/chains", params={"limit": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["flags"]) == 2
    # summary still reflects the full scanned set, not the capped page.
    assert body["summary"]["impossible"] == 5
    assert body["scanned"] == 5
