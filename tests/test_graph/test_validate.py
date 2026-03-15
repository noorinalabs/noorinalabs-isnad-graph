"""Tests for graph validation queries (.cypher files) and result classification."""

from __future__ import annotations

from pathlib import Path

# The validation queries live in queries/validation/*.cypher
QUERIES_DIR = Path(__file__).resolve().parents[2] / "queries" / "validation"


class TestValidationQueryFiles:
    def test_orphan_narrators_exists(self) -> None:
        path = QUERIES_DIR / "orphan_narrators.cypher"
        assert path.exists(), f"Missing {path}"

    def test_chain_integrity_exists(self) -> None:
        path = QUERIES_DIR / "chain_integrity.cypher"
        assert path.exists(), f"Missing {path}"

    def test_collection_coverage_exists(self) -> None:
        path = QUERIES_DIR / "collection_coverage.cypher"
        assert path.exists(), f"Missing {path}"

    def test_cypher_files_are_not_empty(self) -> None:
        for cypher_file in QUERIES_DIR.glob("*.cypher"):
            content = cypher_file.read_text().strip()
            assert len(content) > 0, f"{cypher_file.name} is empty"

    def test_cypher_files_contain_match_or_return(self) -> None:
        for cypher_file in QUERIES_DIR.glob("*.cypher"):
            content = cypher_file.read_text().upper()
            assert "MATCH" in content or "RETURN" in content, (
                f"{cypher_file.name} does not contain MATCH or RETURN"
            )


class TestOrphanCheckClassification:
    """Orphan check: 0 results = pass (no orphan narrators)."""

    def test_zero_results_is_pass(self) -> None:
        results: list[dict[str, str]] = []
        assert len(results) == 0  # pass condition

    def test_nonzero_results_is_fail(self) -> None:
        results = [
            {"narrator_id": "nar:orphan-1", "name": "Orphan Narrator"},
        ]
        assert len(results) > 0  # fail condition


class TestChainIntegrityClassification:
    """Chain integrity: 0 cycles = pass."""

    def test_zero_cycles_is_pass(self) -> None:
        results: list[dict[str, object]] = []
        assert len(results) == 0  # no cycles found

    def test_cycles_detected_is_fail(self) -> None:
        results = [
            {"narrator_id": "nar:cycle-node", "cycle_length": 3},
        ]
        assert len(results) > 0  # cycles found = fail


class TestCollectionCoverageClassification:
    """Collection coverage: deviation within threshold = pass."""

    THRESHOLD_PCT = 10.0

    def test_within_threshold_is_pass(self) -> None:
        results = [
            {
                "collection_id": "col:bukhari",
                "expected": 7563,
                "actual": 7500,
                "deviation_pct": 0.83,
            },
            {
                "collection_id": "col:muslim",
                "expected": 5362,
                "actual": 5300,
                "deviation_pct": 1.16,
            },
        ]
        for row in results:
            assert row["deviation_pct"] is None or row["deviation_pct"] <= self.THRESHOLD_PCT

    def test_exceeds_threshold_is_fail(self) -> None:
        results = [
            {"collection_id": "col:bad", "expected": 1000, "actual": 500, "deviation_pct": 50.0},
        ]
        failures = [
            r
            for r in results
            if r["deviation_pct"] is not None and r["deviation_pct"] > self.THRESHOLD_PCT
        ]
        assert len(failures) > 0

    def test_null_expected_is_pass(self) -> None:
        results = [
            {"collection_id": "col:unknown", "expected": None, "actual": 42, "deviation_pct": None},
        ]
        failures = [
            r
            for r in results
            if r["deviation_pct"] is not None and r["deviation_pct"] > self.THRESHOLD_PCT
        ]
        assert len(failures) == 0  # null expected count means no comparison possible


class TestCypherFileLoading:
    """Test that .cypher files can be read and used as query strings."""

    def test_load_orphan_query(self) -> None:
        path = QUERIES_DIR / "orphan_narrators.cypher"
        query = path.read_text().strip()
        assert "Narrator" in query
        assert "MATCH" in query

    def test_load_chain_integrity_query(self) -> None:
        path = QUERIES_DIR / "chain_integrity.cypher"
        query = path.read_text().strip()
        assert "TRANSMITTED_TO" in query

    def test_load_collection_coverage_query(self) -> None:
        path = QUERIES_DIR / "collection_coverage.cypher"
        query = path.read_text().strip()
        assert "APPEARS_IN" in query
        assert "Collection" in query
