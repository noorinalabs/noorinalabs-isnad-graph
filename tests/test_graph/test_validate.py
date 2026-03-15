"""Tests for graph validation queries (.cypher files) and result classification."""

from __future__ import annotations

from pathlib import Path

from src.graph.validate import _classify

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
        result = _classify("orphan_narrators", [])
        assert result.passed is True
        assert result.row_count == 0

    def test_nonzero_results_is_fail(self) -> None:
        rows: list[dict[str, object]] = [
            {"narrator_id": "nar:orphan-1", "name": "Orphan Narrator"},
        ]
        result = _classify("orphan_narrators", rows)
        assert result.passed is False
        assert result.row_count == 1


class TestChainIntegrityClassification:
    """Chain integrity: 0 cycles = pass."""

    def test_zero_cycles_is_pass(self) -> None:
        result = _classify("chain_integrity", [])
        assert result.passed is True
        assert result.row_count == 0

    def test_cycles_detected_is_fail(self) -> None:
        rows: list[dict[str, object]] = [
            {"narrator_id": "nar:cycle-node", "cycle_length": 3},
        ]
        result = _classify("chain_integrity", rows)
        assert result.passed is False
        assert result.row_count == 1


class TestCollectionCoverageClassification:
    """Collection coverage: deviation within threshold = pass."""

    def test_within_threshold_is_pass(self) -> None:
        rows: list[dict[str, object]] = [
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
        result = _classify("collection_coverage", rows)
        assert result.passed is True

    def test_exceeds_threshold_is_fail(self) -> None:
        rows: list[dict[str, object]] = [
            {"collection_id": "col:bad", "expected": 1000, "actual": 500, "deviation_pct": 50.0},
        ]
        result = _classify("collection_coverage", rows)
        assert result.passed is False

    def test_null_expected_is_pass(self) -> None:
        rows: list[dict[str, object]] = [
            {"collection_id": "col:unknown", "expected": None, "actual": 42, "deviation_pct": None},
        ]
        result = _classify("collection_coverage", rows)
        assert result.passed is True


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
