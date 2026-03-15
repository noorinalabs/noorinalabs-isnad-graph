"""Graph validation query runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.utils.logging import get_logger
from src.utils.neo4j_client import Neo4jClient

logger = get_logger(__name__)

__all__ = ["run_validation", "ValidationResult"]

_DEFAULT_DEVIATION_THRESHOLD = 10.0


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of a single validation query."""

    query_name: str
    passed: bool
    details: str
    row_count: int


def _classify(
    query_name: str,
    rows: list[dict[str, object]],
    *,
    deviation_threshold: float = _DEFAULT_DEVIATION_THRESHOLD,
) -> ValidationResult:
    """Classify query results as pass/fail based on query semantics."""
    count = len(rows)

    if query_name == "orphan_narrators":
        passed = count == 0
        details = "no orphans" if passed else f"{count} orphan narrator(s) found"
        return ValidationResult(query_name, passed, details, count)

    if query_name == "chain_integrity":
        passed = count == 0
        details = "no cycles" if passed else f"{count} cycle(s) detected"
        return ValidationResult(query_name, passed, details, count)

    if query_name == "collection_coverage":
        failures: list[str] = []
        for row in rows:
            dev = row.get("deviation_pct")
            if dev is not None and isinstance(dev, (int, float)) and dev > deviation_threshold:
                cid = row.get("collection_id", "?")
                failures.append(f"{cid}: {dev:.1f}% deviation")
        passed = len(failures) == 0
        details = "all within threshold" if passed else "; ".join(failures)
        return ValidationResult(query_name, passed, details, count)

    # Unknown query — pass if 0 rows (conservative default)
    passed = count == 0
    details = f"{count} row(s) returned" if count else "empty result"
    return ValidationResult(query_name, passed, details, count)


def run_validation(
    client: Neo4jClient,
    queries_dir: Path,
    *,
    deviation_threshold: float = _DEFAULT_DEVIATION_THRESHOLD,
) -> list[ValidationResult]:
    """Run all ``.cypher`` files in ``queries_dir/validation/``.

    Parameters
    ----------
    client:
        Connected Neo4j client.
    queries_dir:
        Root queries directory (must contain a ``validation/`` subdirectory).
    deviation_threshold:
        Maximum acceptable deviation percentage for collection coverage.

    Returns
    -------
    list[ValidationResult]
        One result per query file executed.
    """
    validation_dir = queries_dir / "validation"
    if not validation_dir.is_dir():
        logger.warning("validation_dir_missing", path=str(validation_dir))
        return []

    cypher_files = sorted(validation_dir.glob("*.cypher"))
    if not cypher_files:
        logger.warning("no_validation_queries", path=str(validation_dir))
        return []

    results: list[ValidationResult] = []
    for fp in cypher_files:
        query_name = fp.stem
        cypher_text = fp.read_text(encoding="utf-8").strip()
        if not cypher_text:
            logger.warning("empty_cypher_file", file=fp.name)
            continue

        logger.info("validation_running", query=query_name)
        try:
            rows = client.execute_read(cypher_text)
        except Exception:
            logger.exception("validation_query_failed", query=query_name)
            results.append(
                ValidationResult(
                    query_name, passed=False, details="query execution failed", row_count=0
                )
            )
            continue

        result = _classify(query_name, rows, deviation_threshold=deviation_threshold)
        status = "PASS" if result.passed else "FAIL"
        logger.info(
            "validation_complete",
            query=query_name,
            status=status,
            rows=result.row_count,
            details=result.details,
        )
        results.append(result)

    return results
