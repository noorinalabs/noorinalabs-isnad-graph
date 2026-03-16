"""Neo4j edge/relationship loading.

Batch UNWIND loaders for 6 relationship types: TRANSMITTED_TO, NARRATED,
APPEARS_IN, PARALLEL_OF, STUDIED_UNDER, and GRADED_BY.  Each loader uses
MATCH (not MERGE) for endpoints, logging and counting missing endpoints
rather than silently creating dangling references.  Edge creation uses MERGE
for idempotent re-runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from src.utils.logging import get_logger
from src.utils.neo4j_client import Neo4jClient

logger = get_logger(__name__)

__all__ = ["load_all_edges", "EdgeLoadResult"]

DEFAULT_BATCH_SIZE = 1000


@dataclass(frozen=True)
class EdgeLoadResult:
    """Outcome of loading a single edge/relationship type."""

    edge_type: str
    created: int
    skipped: int
    missing_endpoints: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _transpose_pydict(col_dict: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Convert column-oriented dict ``{col: [vals]}`` to ``[{col: val}, ...]``."""
    if not col_dict:
        return []
    keys = list(col_dict.keys())
    n = len(col_dict[keys[0]])
    return [{k: col_dict[k][i] for k in keys} for i in range(n)]


def _chunked_read(
    client: Neo4jClient,
    query: str,
    batch: list[dict[str, Any]],
    batch_size: int,
) -> list[dict[str, Any]]:
    """Execute a read query in chunks to avoid memory issues at scale."""
    results: list[dict[str, Any]] = []
    for i in range(0, len(batch), batch_size):
        chunk = batch[i : i + batch_size]
        results.extend(client.execute_read(query, {"batch": chunk}))
    return results


def _read_parquet_rows(path: Path) -> list[dict[str, Any]]:
    """Read a Parquet file and return row dicts."""
    table = pq.read_table(path)
    return _transpose_pydict(table.to_pydict())


def _parquet_files(directory: Path, prefix: str) -> list[Path]:
    """Return sorted parquet files matching *prefix* in *directory*."""
    return sorted(directory.glob(f"{prefix}*.parquet"))


def _val(row: dict[str, Any], key: str, default: Any = None) -> Any:
    """Get a value from *row*, returning *default* for ``None``."""
    v = row.get(key)
    return default if v is None else v


# ---------------------------------------------------------------------------
# 1. TRANSMITTED_TO — consecutive narrator pairs in each chain
# ---------------------------------------------------------------------------

_TRANSMITTED_TO_QUERY = """\
UNWIND $batch AS row
MATCH (n1:Narrator {id: row.from_id})
MATCH (n2:Narrator {id: row.to_id})
MERGE (n1)-[:TRANSMITTED_TO {
    position_in_chain: row.position,
    hadith_id: row.hadith_id
}]->(n2)
"""

_TRANSMITTED_TO_CHECK = """\
UNWIND $batch AS row
OPTIONAL MATCH (n1:Narrator {id: row.from_id})
OPTIONAL MATCH (n2:Narrator {id: row.to_id})
RETURN row.from_id AS from_id,
       row.to_id AS to_id,
       n1 IS NOT NULL AS from_exists,
       n2 IS NOT NULL AS to_exists
"""


def _build_chain_pairs(
    mentions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build consecutive narrator pairs from sorted chain mentions.

    Each mention must have ``canonical_narrator_id``, ``position_in_chain``,
    and ``hadith_id``.  Returns dicts with ``from_id``, ``to_id``,
    ``position``, and ``hadith_id``.
    """
    sorted_mentions = sorted(mentions, key=lambda r: r.get("position_in_chain", 0))
    # Filter to mentions with resolved narrator IDs
    resolved = [m for m in sorted_mentions if m.get("canonical_narrator_id")]
    pairs: list[dict[str, Any]] = []
    for i in range(len(resolved) - 1):
        pairs.append(
            {
                "from_id": resolved[i]["canonical_narrator_id"],
                "to_id": resolved[i + 1]["canonical_narrator_id"],
                "position": resolved[i].get("position_in_chain", i),
                "hadith_id": resolved[i].get("hadith_id", ""),
            }
        )
    return pairs


def _load_transmitted_to(
    client: Neo4jClient,
    staging_dir: Path,
    *,
    strict: bool = True,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> EdgeLoadResult:
    """Load TRANSMITTED_TO edges from narrator_mentions_resolved.parquet."""
    files = _parquet_files(staging_dir, "narrator_mentions_resolved")
    if not files:
        files = _parquet_files(staging_dir, "narrator_mentions_")
    if not files:
        if strict:
            msg = f"No narrator_mentions files in {staging_dir}"
            raise FileNotFoundError(msg)
        logger.warning("transmitted_to_files_missing", dir=str(staging_dir))
        return EdgeLoadResult("TRANSMITTED_TO", 0, 0, 0)

    # Group mentions by hadith
    by_hadith: dict[str, list[dict[str, Any]]] = {}
    for fp in files:
        rows = _read_parquet_rows(fp)
        for row in rows:
            hid = row.get("hadith_id") or row.get("source_hadith_id")
            if not hid:
                continue
            by_hadith.setdefault(hid, []).append(row)

    # Build all chain pairs
    all_pairs: list[dict[str, Any]] = []
    for hid, mentions in by_hadith.items():
        all_pairs.extend(_build_chain_pairs(mentions))

    if not all_pairs:
        logger.info("transmitted_to_no_pairs")
        return EdgeLoadResult("TRANSMITTED_TO", 0, 0, 0)

    # Check for missing endpoints
    check_results = _chunked_read(client, _TRANSMITTED_TO_CHECK, all_pairs, batch_size)
    valid_batch: list[dict[str, Any]] = []
    missing = 0
    for pair, check in zip(all_pairs, check_results):
        if check.get("from_exists") and check.get("to_exists"):
            valid_batch.append(pair)
        else:
            missing += 1
            if not check.get("from_exists"):
                logger.debug("transmitted_to_missing_from", id=pair["from_id"])
            if not check.get("to_exists"):
                logger.debug("transmitted_to_missing_to", id=pair["to_id"])

    created = (
        client.execute_write_batch(_TRANSMITTED_TO_QUERY, valid_batch, batch_size=batch_size)
        if valid_batch
        else 0
    )
    logger.info(
        "transmitted_to_loaded",
        created=created,
        missing_endpoints=missing,
        total_pairs=len(all_pairs),
    )
    return EdgeLoadResult("TRANSMITTED_TO", created, 0, missing)


# ---------------------------------------------------------------------------
# 2. NARRATED — first narrator in each chain → hadith
# ---------------------------------------------------------------------------

_NARRATED_QUERY = """\
UNWIND $batch AS row
MATCH (n:Narrator {id: row.narrator_id})
MATCH (h:Hadith {id: row.hadith_id})
MERGE (n)-[:NARRATED]->(h)
"""

_NARRATED_CHECK = """\
UNWIND $batch AS row
OPTIONAL MATCH (n:Narrator {id: row.narrator_id})
OPTIONAL MATCH (h:Hadith {id: row.hadith_id})
RETURN row.narrator_id AS narrator_id,
       row.hadith_id AS hadith_id,
       n IS NOT NULL AS narrator_exists,
       h IS NOT NULL AS hadith_exists
"""


def _load_narrated(
    client: Neo4jClient,
    staging_dir: Path,
    *,
    strict: bool = True,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> EdgeLoadResult:
    """Load NARRATED edges — first narrator (position 0) in each chain → hadith."""
    files = _parquet_files(staging_dir, "narrator_mentions_resolved")
    if not files:
        files = _parquet_files(staging_dir, "narrator_mentions_")
    if not files:
        if strict:
            msg = f"No narrator_mentions files in {staging_dir}"
            raise FileNotFoundError(msg)
        logger.warning("narrated_files_missing", dir=str(staging_dir))
        return EdgeLoadResult("NARRATED", 0, 0, 0)

    # Find position-0 narrator per hadith (lowest position_in_chain)
    first_narrators: dict[str, tuple[int, str]] = {}  # hid -> (pos, narrator_id)
    for fp in files:
        rows = _read_parquet_rows(fp)
        for row in rows:
            hid = row.get("hadith_id") or row.get("source_hadith_id")
            nid = row.get("canonical_narrator_id")
            pos = row.get("position_in_chain", 0)
            if not hid or not nid:
                continue
            if hid not in first_narrators or pos < first_narrators[hid][0]:
                first_narrators[hid] = (pos, nid)

    batch: list[dict[str, Any]] = []
    for hid, (_pos, nid) in first_narrators.items():
        full_hid = f"hdt:{hid}" if not hid.startswith("hdt:") else hid
        batch.append({"narrator_id": nid, "hadith_id": full_hid})

    if not batch:
        logger.info("narrated_no_edges")
        return EdgeLoadResult("NARRATED", 0, 0, 0)

    # Check endpoints
    check_results = _chunked_read(client, _NARRATED_CHECK, batch, batch_size)
    valid_batch: list[dict[str, Any]] = []
    missing = 0
    for item, check in zip(batch, check_results):
        if check.get("narrator_exists") and check.get("hadith_exists"):
            valid_batch.append(item)
        else:
            missing += 1

    created = (
        client.execute_write_batch(_NARRATED_QUERY, valid_batch, batch_size=batch_size)
        if valid_batch
        else 0
    )
    logger.info("narrated_loaded", created=created, missing_endpoints=missing)
    return EdgeLoadResult("NARRATED", created, 0, missing)


# ---------------------------------------------------------------------------
# 3. APPEARS_IN — hadith → collection
# ---------------------------------------------------------------------------

_APPEARS_IN_QUERY = """\
UNWIND $batch AS row
MATCH (h:Hadith {id: row.hadith_id})
MATCH (c:Collection {id: row.collection_id})
MERGE (h)-[:APPEARS_IN {
    book_number: row.book_number,
    chapter_number: row.chapter_number,
    hadith_number: row.hadith_number
}]->(c)
"""

_APPEARS_IN_CHECK = """\
UNWIND $batch AS row
OPTIONAL MATCH (h:Hadith {id: row.hadith_id})
OPTIONAL MATCH (c:Collection {id: row.collection_id})
RETURN row.hadith_id AS hadith_id,
       row.collection_id AS collection_id,
       h IS NOT NULL AS hadith_exists,
       c IS NOT NULL AS collection_exists
"""


def _load_appears_in(
    client: Neo4jClient,
    staging_dir: Path,
    *,
    strict: bool = True,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> EdgeLoadResult:
    """Load APPEARS_IN edges — hadith → collection with positional properties."""
    files = _parquet_files(staging_dir, "hadiths_")
    if not files:
        if strict:
            msg = f"No hadiths_*.parquet files in {staging_dir}"
            raise FileNotFoundError(msg)
        logger.warning("appears_in_files_missing", dir=str(staging_dir))
        return EdgeLoadResult("APPEARS_IN", 0, 0, 0)

    batch: list[dict[str, Any]] = []
    skipped = 0

    for fp in files:
        rows = _read_parquet_rows(fp)
        for row in rows:
            sid = row.get("source_id")
            cname = row.get("collection_name")
            if not sid or not cname:
                skipped += 1
                continue
            hid = f"hdt:{sid}" if not sid.startswith("hdt:") else sid
            cid = f"col:{cname}" if not cname.startswith("col:") else cname
            batch.append(
                {
                    "hadith_id": hid,
                    "collection_id": cid,
                    "book_number": _val(row, "book_number"),
                    "chapter_number": _val(row, "chapter_number"),
                    "hadith_number": _val(row, "hadith_number"),
                }
            )

    if not batch:
        logger.info("appears_in_no_edges")
        return EdgeLoadResult("APPEARS_IN", 0, skipped, 0)

    # Check endpoints
    check_results = _chunked_read(client, _APPEARS_IN_CHECK, batch, batch_size)
    valid_batch: list[dict[str, Any]] = []
    missing = 0
    for item, check in zip(batch, check_results):
        if check.get("hadith_exists") and check.get("collection_exists"):
            valid_batch.append(item)
        else:
            missing += 1

    created = (
        client.execute_write_batch(_APPEARS_IN_QUERY, valid_batch, batch_size=batch_size)
        if valid_batch
        else 0
    )
    logger.info("appears_in_loaded", created=created, skipped=skipped, missing_endpoints=missing)
    return EdgeLoadResult("APPEARS_IN", created, skipped, missing)


# ---------------------------------------------------------------------------
# 4. PARALLEL_OF — from parallel_links.parquet
# ---------------------------------------------------------------------------

_PARALLEL_OF_QUERY = """\
UNWIND $batch AS row
MATCH (h1:Hadith {id: row.id_a})
MATCH (h2:Hadith {id: row.id_b})
MERGE (h1)-[:PARALLEL_OF {
    similarity_score: row.score,
    variant_type: row.variant_type,
    cross_sect: row.cross_sect
}]->(h2)
"""

_PARALLEL_OF_CHECK = """\
UNWIND $batch AS row
OPTIONAL MATCH (h1:Hadith {id: row.id_a})
OPTIONAL MATCH (h2:Hadith {id: row.id_b})
RETURN row.id_a AS id_a,
       row.id_b AS id_b,
       h1 IS NOT NULL AS a_exists,
       h2 IS NOT NULL AS b_exists
"""


def _load_parallel_of(
    client: Neo4jClient,
    staging_dir: Path,
    *,
    strict: bool = True,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> EdgeLoadResult:
    """Load PARALLEL_OF edges from parallel_links.parquet."""
    path = staging_dir / "parallel_links.parquet"
    if not path.exists():
        if strict:
            msg = f"Missing required file: {path}"
            raise FileNotFoundError(msg)
        logger.warning("parallel_links_missing", path=str(path))
        return EdgeLoadResult("PARALLEL_OF", 0, 0, 0)

    rows = _read_parquet_rows(path)
    batch: list[dict[str, Any]] = []
    skipped = 0

    for row in rows:
        id_a = row.get("hadith_id_a")
        id_b = row.get("hadith_id_b")
        if not id_a or not id_b:
            skipped += 1
            continue
        # Ensure lower ID → higher ID for consistent directionality
        full_a = f"hdt:{id_a}" if not id_a.startswith("hdt:") else id_a
        full_b = f"hdt:{id_b}" if not id_b.startswith("hdt:") else id_b
        if full_a > full_b:
            full_a, full_b = full_b, full_a
        batch.append(
            {
                "id_a": full_a,
                "id_b": full_b,
                "score": _val(row, "similarity_score", 0.0),
                "variant_type": _val(row, "variant_type", "unknown"),
                "cross_sect": _val(row, "cross_sect", False),
            }
        )

    if not batch:
        logger.info("parallel_of_no_edges")
        return EdgeLoadResult("PARALLEL_OF", 0, skipped, 0)

    # Check endpoints
    check_results = _chunked_read(client, _PARALLEL_OF_CHECK, batch, batch_size)
    valid_batch: list[dict[str, Any]] = []
    missing = 0
    for item, check in zip(batch, check_results):
        if check.get("a_exists") and check.get("b_exists"):
            valid_batch.append(item)
        else:
            missing += 1

    created = (
        client.execute_write_batch(_PARALLEL_OF_QUERY, valid_batch, batch_size=batch_size)
        if valid_batch
        else 0
    )
    logger.info("parallel_of_loaded", created=created, skipped=skipped, missing_endpoints=missing)
    return EdgeLoadResult("PARALLEL_OF", created, skipped, missing)


# ---------------------------------------------------------------------------
# 5. STUDIED_UNDER — from network_edges_muhaddithat.parquet
# ---------------------------------------------------------------------------

_STUDIED_UNDER_QUERY = """\
UNWIND $batch AS row
MATCH (s:Narrator {id: row.from_id})
MATCH (t:Narrator {id: row.to_id})
MERGE (s)-[:STUDIED_UNDER]->(t)
"""

_STUDIED_UNDER_CHECK = """\
UNWIND $batch AS row
OPTIONAL MATCH (s:Narrator {id: row.from_id})
OPTIONAL MATCH (t:Narrator {id: row.to_id})
RETURN row.from_id AS from_id,
       row.to_id AS to_id,
       s IS NOT NULL AS from_exists,
       t IS NOT NULL AS to_exists
"""


def _load_studied_under(
    client: Neo4jClient,
    staging_dir: Path,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> EdgeLoadResult:
    """Load STUDIED_UNDER edges from network_edges_muhaddithat.parquet.

    Gracefully skips if file does not exist.
    """
    path = staging_dir / "network_edges_muhaddithat.parquet"
    if not path.exists():
        logger.info("studied_under_skipped", reason="file_not_found", path=str(path))
        return EdgeLoadResult("STUDIED_UNDER", 0, 0, 0)

    rows = _read_parquet_rows(path)
    batch: list[dict[str, Any]] = []
    skipped = 0

    for row in rows:
        from_id = row.get("from_external_id") or row.get("from_narrator_name")
        to_id = row.get("to_external_id") or row.get("to_narrator_name")
        if not from_id or not to_id:
            skipped += 1
            continue
        # Ensure narrator prefix
        full_from = f"nar:{from_id}" if not from_id.startswith("nar:") else from_id
        full_to = f"nar:{to_id}" if not to_id.startswith("nar:") else to_id
        batch.append({"from_id": full_from, "to_id": full_to})

    if not batch:
        logger.info("studied_under_no_edges")
        return EdgeLoadResult("STUDIED_UNDER", 0, skipped, 0)

    # Check endpoints
    check_results = _chunked_read(client, _STUDIED_UNDER_CHECK, batch, batch_size)
    valid_batch: list[dict[str, Any]] = []
    missing = 0
    for item, check in zip(batch, check_results):
        if check.get("from_exists") and check.get("to_exists"):
            valid_batch.append(item)
        else:
            missing += 1

    created = (
        client.execute_write_batch(_STUDIED_UNDER_QUERY, valid_batch, batch_size=batch_size)
        if valid_batch
        else 0
    )
    logger.info("studied_under_loaded", created=created, skipped=skipped, missing_endpoints=missing)
    return EdgeLoadResult("STUDIED_UNDER", created, skipped, missing)


# ---------------------------------------------------------------------------
# 6. GRADED_BY — hadith → grading
# ---------------------------------------------------------------------------

_GRADED_BY_QUERY = """\
UNWIND $batch AS row
MATCH (h:Hadith {id: row.hadith_id})
MATCH (g:Grading {id: row.grading_id})
MERGE (h)-[:GRADED_BY]->(g)
"""

_GRADED_BY_CHECK = """\
UNWIND $batch AS row
OPTIONAL MATCH (h:Hadith {id: row.hadith_id})
OPTIONAL MATCH (g:Grading {id: row.grading_id})
RETURN row.hadith_id AS hadith_id,
       row.grading_id AS grading_id,
       h IS NOT NULL AS hadith_exists,
       g IS NOT NULL AS grading_exists
"""


def _load_graded_by(
    client: Neo4jClient,
    staging_dir: Path,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> EdgeLoadResult:
    """Load GRADED_BY edges from hadith staging data.

    Gracefully skips if no hadiths with grades exist.
    """
    files = _parquet_files(staging_dir, "hadiths_")
    if not files:
        logger.info("graded_by_skipped", reason="no_hadith_files")
        return EdgeLoadResult("GRADED_BY", 0, 0, 0)

    batch: list[dict[str, Any]] = []
    skipped = 0

    for fp in files:
        rows = _read_parquet_rows(fp)
        for row in rows:
            grade = row.get("grade")
            if not grade:
                continue
            sid = row.get("source_id")
            if not sid:
                skipped += 1
                continue
            hid = f"hdt:{sid}" if not sid.startswith("hdt:") else sid
            gid = f"grd:{sid}"
            batch.append({"hadith_id": hid, "grading_id": gid})

    if not batch:
        logger.info("graded_by_no_edges")
        return EdgeLoadResult("GRADED_BY", 0, skipped, 0)

    # Check endpoints
    check_results = _chunked_read(client, _GRADED_BY_CHECK, batch, batch_size)
    valid_batch: list[dict[str, Any]] = []
    missing = 0
    for item, check in zip(batch, check_results):
        if check.get("hadith_exists") and check.get("grading_exists"):
            valid_batch.append(item)
        else:
            missing += 1

    created = (
        client.execute_write_batch(_GRADED_BY_QUERY, valid_batch, batch_size=batch_size)
        if valid_batch
        else 0
    )
    logger.info("graded_by_loaded", created=created, skipped=skipped, missing_endpoints=missing)
    return EdgeLoadResult("GRADED_BY", created, skipped, missing)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def load_all_edges(
    client: Neo4jClient,
    staging_dir: Path,
    curated_dir: Path,  # noqa: ARG001
    *,
    strict: bool = True,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[EdgeLoadResult]:
    """Load all edge/relationship types into Neo4j.

    Parameters
    ----------
    client:
        Connected Neo4j client.
    staging_dir:
        Directory containing staging Parquet files.
    curated_dir:
        Directory containing curated reference data (unused for edges
        currently but kept for API symmetry with ``load_all_nodes``).
    strict:
        If ``True``, raise on missing required files. If ``False``,
        skip gracefully.
    batch_size:
        Number of edges per batch for both read checks and writes.
    """
    results: list[EdgeLoadResult] = []

    results.append(_load_transmitted_to(client, staging_dir, strict=strict, batch_size=batch_size))
    results.append(_load_narrated(client, staging_dir, strict=strict, batch_size=batch_size))
    results.append(_load_appears_in(client, staging_dir, strict=strict, batch_size=batch_size))
    results.append(_load_parallel_of(client, staging_dir, strict=strict, batch_size=batch_size))
    results.append(_load_studied_under(client, staging_dir, batch_size=batch_size))
    results.append(_load_graded_by(client, staging_dir, batch_size=batch_size))

    total_created = sum(r.created for r in results)
    total_missing = sum(r.missing_endpoints for r in results)
    logger.info(
        "all_edges_loaded",
        total_created=total_created,
        total_missing_endpoints=total_missing,
        edge_types=len(results),
    )
    return results
