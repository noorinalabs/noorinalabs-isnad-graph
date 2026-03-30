"""Neo4j node loading for all graph node types.

Batch UNWIND+MERGE loaders for Narrator, Hadith, Collection, Chain,
Grading, HistoricalEvent, and Location nodes.  Each loader reads from
staging/curated Parquet or YAML, validates rows, and merges into Neo4j
with explicit property SET (no ``SET n += row``) for Phase 4 safety.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml

from src.utils.logging import get_logger
from src.utils.neo4j_client import Neo4jClient

logger = get_logger(__name__)

__all__ = ["load_all_nodes", "LoadResult"]


@dataclass(frozen=True)
class LoadResult:
    """Outcome of loading a single node type."""

    node_type: str
    created: int
    merged: int
    skipped: int
    validation_errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parquet_files(directory: Path, prefix: str) -> list[Path]:
    """Return sorted parquet files matching *prefix* in *directory*."""
    return sorted(directory.glob(f"{prefix}*.parquet"))


def _read_parquet_rows(path: Path) -> list[dict[str, Any]]:
    """Read a Parquet file and return row dicts."""
    table = pq.read_table(path)
    rows: list[dict[str, Any]] = table.to_pylist()
    return rows


def _val(row: dict[str, Any], key: str, default: Any = None) -> Any:
    """Get a value from *row*, returning *default* for ``None``."""
    v = row.get(key)
    return default if v is None else v


# ---------------------------------------------------------------------------
# Narrator loader
# ---------------------------------------------------------------------------

_NARRATOR_MERGE = """\
UNWIND $batch AS row
MERGE (n:Narrator {id: row.id})
SET n.name_ar           = row.name_ar,
    n.name_en           = row.name_en,
    n.name_ar_normalized = row.name_ar_normalized,
    n.birth_year_ah     = row.birth_year_ah,
    n.death_year_ah     = row.death_year_ah,
    n.generation        = row.generation,
    n.gender            = row.gender,
    n.trustworthiness   = row.trustworthiness,
    n.aliases           = row.aliases,
    n.external_id       = row.external_id,
    n.mention_count     = row.mention_count
"""


def _load_narrators(
    client: Neo4jClient,
    staging_dir: Path,
    curated_dir: Path,
    *,
    strict: bool = True,
) -> LoadResult:
    """Load Narrator nodes from narrators_canonical.parquet."""
    path = staging_dir / "narrators_canonical.parquet"
    if not path.exists():
        if strict:
            msg = f"Missing required file: {path}"
            raise FileNotFoundError(msg)
        logger.warning("narrator_file_missing", path=str(path))
        return LoadResult("Narrator", 0, 0, 0)

    rows = _read_parquet_rows(path)
    batch: list[dict[str, Any]] = []
    errors: list[str] = []
    skipped = 0

    for i, row in enumerate(rows):
        cid = row.get("canonical_id")
        if not cid or not isinstance(cid, str) or not cid.startswith("nar:"):
            errors.append(f"row {i}: invalid canonical_id={cid!r}")
            skipped += 1
            continue
        batch.append(
            {
                "id": cid,
                "name_ar": _val(row, "name_ar", ""),
                "name_en": _val(row, "name_en", ""),
                "name_ar_normalized": _val(row, "name_ar_normalized"),
                "birth_year_ah": _val(row, "birth_year_ah"),
                "death_year_ah": _val(row, "death_year_ah"),
                "generation": _val(row, "generation"),
                "gender": _val(row, "gender"),
                "trustworthiness": _val(row, "trustworthiness"),
                "aliases": _val(row, "aliases", []),
                "external_id": _val(row, "external_id"),
                "mention_count": _val(row, "mention_count"),
            }
        )

    created = client.execute_write_batch(_NARRATOR_MERGE, batch) if batch else 0
    merged = len(batch) - created
    logger.info(
        "narrators_loaded",
        created=created,
        merged=merged,
        skipped=skipped,
        errors=len(errors),
    )
    return LoadResult("Narrator", created, merged, skipped, errors)


# ---------------------------------------------------------------------------
# Hadith loader
# ---------------------------------------------------------------------------

_HADITH_MERGE = """\
UNWIND $batch AS row
MERGE (n:Hadith {id: row.id})
SET n.matn_ar      = row.matn_ar,
    n.matn_en      = row.matn_en,
    n.isnad_raw_ar = row.isnad_raw_ar,
    n.isnad_raw_en = row.isnad_raw_en,
    n.grade        = row.grade,
    n.source_corpus = row.source_corpus,
    n.sect         = row.sect,
    n.collection_name = row.collection_name,
    n.book_number  = row.book_number,
    n.chapter_number = row.chapter_number,
    n.hadith_number = row.hadith_number
"""


def _load_hadiths(
    client: Neo4jClient,
    staging_dir: Path,
    *,
    strict: bool = True,
) -> LoadResult:
    """Load Hadith nodes from hadiths_*.parquet files."""
    files = _parquet_files(staging_dir, "hadiths_")
    if not files:
        if strict:
            msg = f"No hadiths_*.parquet files in {staging_dir}"
            raise FileNotFoundError(msg)
        logger.warning("hadith_files_missing", dir=str(staging_dir))
        return LoadResult("Hadith", 0, 0, 0)

    total_created = 0
    total_skipped = 0
    all_errors: list[str] = []
    total_batch = 0

    for fp in files:
        rows = _read_parquet_rows(fp)
        batch: list[dict[str, Any]] = []
        for i, row in enumerate(rows):
            sid = row.get("source_id")
            if not sid or not isinstance(sid, str):
                all_errors.append(f"{fp.name} row {i}: invalid source_id={sid!r}")
                total_skipped += 1
                continue
            hid = f"hdt:{sid}" if not sid.startswith("hdt:") else sid
            batch.append(
                {
                    "id": hid,
                    "matn_ar": _val(row, "matn_ar", ""),
                    "matn_en": _val(row, "matn_en"),
                    "isnad_raw_ar": _val(row, "isnad_raw_ar"),
                    "isnad_raw_en": _val(row, "isnad_raw_en"),
                    "grade": _val(row, "grade"),
                    "source_corpus": _val(row, "source_corpus", ""),
                    "sect": _val(row, "sect", ""),
                    "collection_name": _val(row, "collection_name", ""),
                    "book_number": _val(row, "book_number"),
                    "chapter_number": _val(row, "chapter_number"),
                    "hadith_number": _val(row, "hadith_number"),
                }
            )
        if batch:
            total_created += client.execute_write_batch(_HADITH_MERGE, batch)
            total_batch += len(batch)

    merged = total_batch - total_created
    logger.info(
        "hadiths_loaded",
        files=len(files),
        created=total_created,
        merged=merged,
        skipped=total_skipped,
    )
    return LoadResult("Hadith", total_created, merged, total_skipped, all_errors)


# ---------------------------------------------------------------------------
# Collection loader
# ---------------------------------------------------------------------------

_COLLECTION_MERGE = """\
UNWIND $batch AS row
MERGE (n:Collection {id: row.id})
SET n.name_ar            = row.name_ar,
    n.name_en            = row.name_en,
    n.compiler_name      = row.compiler_name,
    n.compilation_year_ah = row.compilation_year_ah,
    n.sect               = row.sect,
    n.total_hadiths      = row.total_hadiths,
    n.source_corpus      = row.source_corpus
"""


def _load_collections(
    client: Neo4jClient,
    staging_dir: Path,
    *,
    strict: bool = True,
) -> LoadResult:
    """Load Collection nodes from collections_*.parquet files."""
    files = _parquet_files(staging_dir, "collections_")
    if not files:
        if strict:
            msg = f"No collections_*.parquet files in {staging_dir}"
            raise FileNotFoundError(msg)
        logger.warning("collection_files_missing", dir=str(staging_dir))
        return LoadResult("Collection", 0, 0, 0)

    total_created = 0
    total_skipped = 0
    all_errors: list[str] = []
    total_batch = 0

    for fp in files:
        rows = _read_parquet_rows(fp)
        batch: list[dict[str, Any]] = []
        for i, row in enumerate(rows):
            cid = row.get("collection_id")
            if not cid or not isinstance(cid, str):
                all_errors.append(f"{fp.name} row {i}: invalid collection_id={cid!r}")
                total_skipped += 1
                continue
            full_id = f"col:{cid}" if not cid.startswith("col:") else cid
            batch.append(
                {
                    "id": full_id,
                    "name_ar": _val(row, "name_ar"),
                    "name_en": _val(row, "name_en", ""),
                    "compiler_name": _val(row, "compiler_name"),
                    "compilation_year_ah": _val(row, "compilation_year_ah"),
                    "sect": _val(row, "sect", ""),
                    "total_hadiths": _val(row, "total_hadiths"),
                    "source_corpus": _val(row, "source_corpus", ""),
                }
            )
        if batch:
            total_created += client.execute_write_batch(_COLLECTION_MERGE, batch)
            total_batch += len(batch)

    merged = total_batch - total_created
    logger.info(
        "collections_loaded",
        files=len(files),
        created=total_created,
        merged=merged,
        skipped=total_skipped,
    )
    return LoadResult("Collection", total_created, merged, total_skipped, all_errors)


# ---------------------------------------------------------------------------
# Chain loader
# ---------------------------------------------------------------------------

_CHAIN_MERGE = """\
UNWIND $batch AS row
MERGE (n:Chain {id: row.id})
SET n.hadith_id           = row.hadith_id,
    n.chain_index         = row.chain_index,
    n.full_chain_text_ar  = row.full_chain_text_ar,
    n.full_chain_text_en  = row.full_chain_text_en,
    n.chain_length        = row.chain_length,
    n.is_complete         = row.is_complete,
    n.is_elevated         = row.is_elevated,
    n.classification      = row.classification,
    n.narrator_ids        = row.narrator_ids
"""


def _load_chains(
    client: Neo4jClient,
    staging_dir: Path,
    *,
    strict: bool = True,
) -> LoadResult:
    """Load Chain nodes from narrator_mentions resolved data.

    Chains are synthesized from narrator-mention parquet files: each unique
    (hadith_id, chain_index=0) tuple produces a Chain node.  In Phase 3
    wave-1 we create placeholder chains with metadata derived from the
    mentions themselves; full chain enrichment happens in Phase 4.
    """
    files = _parquet_files(staging_dir, "narrator_mentions_")
    if not files:
        if strict:
            msg = f"No narrator_mentions_*.parquet files in {staging_dir}"
            raise FileNotFoundError(msg)
        logger.warning("chain_files_missing", dir=str(staging_dir))
        return LoadResult("Chain", 0, 0, 0)

    seen_hadiths: dict[str, list[dict[str, Any]]] = {}
    for fp in files:
        rows = _read_parquet_rows(fp)
        for row in rows:
            hid = row.get("source_hadith_id") or row.get("hadith_id")
            if not hid:
                continue
            seen_hadiths.setdefault(hid, []).append(row)

    batch: list[dict[str, Any]] = []
    errors: list[str] = []
    skipped = 0

    for hid, mentions in seen_hadiths.items():
        chn_id = f"chn:{hid}-0" if not hid.startswith("chn:") else hid
        narrator_ids = []
        for m in sorted(mentions, key=lambda r: r.get("position_in_chain", 0)):
            nid = m.get("canonical_narrator_id")
            if nid:
                narrator_ids.append(nid)
        batch.append(
            {
                "id": chn_id,
                "hadith_id": f"hdt:{hid}" if not hid.startswith("hdt:") else hid,
                "chain_index": 0,
                "full_chain_text_ar": None,
                "full_chain_text_en": None,
                "chain_length": len(narrator_ids),
                "is_complete": len(narrator_ids) > 0,
                "is_elevated": False,
                "classification": "unknown",
                "narrator_ids": narrator_ids,
            }
        )

    created = client.execute_write_batch(_CHAIN_MERGE, batch) if batch else 0
    merged = len(batch) - created
    logger.info("chains_loaded", created=created, merged=merged, skipped=skipped)
    return LoadResult("Chain", created, merged, skipped, errors)


# ---------------------------------------------------------------------------
# Grading loader
# ---------------------------------------------------------------------------

_GRADING_MERGE = """\
UNWIND $batch AS row
MERGE (n:Grading {id: row.id})
SET n.hadith_id          = row.hadith_id,
    n.scholar_name       = row.scholar_name,
    n.grade              = row.grade,
    n.methodology_school = row.methodology_school,
    n.era                = row.era
"""


def _load_gradings(
    client: Neo4jClient,
    staging_dir: Path,
    *,
    strict: bool = True,
) -> LoadResult:
    """Load Grading nodes from hadith staging data.

    Gradings are extracted from the ``grade`` column of hadiths_*.parquet.
    Each hadith with a non-null grade produces a single Grading node
    attributed to the collection compiler.
    """
    files = _parquet_files(staging_dir, "hadiths_")
    if not files:
        if strict:
            msg = f"No hadiths_*.parquet files for grading extraction in {staging_dir}"
            raise FileNotFoundError(msg)
        logger.warning("grading_files_missing", dir=str(staging_dir))
        return LoadResult("Grading", 0, 0, 0)

    batch: list[dict[str, Any]] = []
    errors: list[str] = []
    skipped = 0

    for fp in files:
        rows = _read_parquet_rows(fp)
        for i, row in enumerate(rows):
            grade = row.get("grade")
            if not grade:
                continue
            sid = row.get("source_id")
            if not sid:
                errors.append(f"{fp.name} row {i}: grade present but no source_id")
                skipped += 1
                continue
            gid = f"grd:{sid}"
            batch.append(
                {
                    "id": gid,
                    "hadith_id": f"hdt:{sid}" if not sid.startswith("hdt:") else sid,
                    "scholar_name": _val(row, "collection_name", "unknown"),
                    "grade": grade,
                    "methodology_school": None,
                    "era": None,
                }
            )

    created = client.execute_write_batch(_GRADING_MERGE, batch) if batch else 0
    merged = len(batch) - created
    logger.info("gradings_loaded", created=created, merged=merged, skipped=skipped)
    return LoadResult("Grading", created, merged, skipped, errors)


# ---------------------------------------------------------------------------
# HistoricalEvent loader
# ---------------------------------------------------------------------------

_EVENT_MERGE = """\
UNWIND $batch AS row
MERGE (n:HistoricalEvent {id: row.id})
SET n.name_en       = row.name_en,
    n.name_ar       = row.name_ar,
    n.year_start_ah = row.year_start_ah,
    n.year_end_ah   = row.year_end_ah,
    n.year_start_ce = row.year_start_ce,
    n.year_end_ce   = row.year_end_ce,
    n.event_type    = row.event_type,
    n.caliphate     = row.caliphate,
    n.region        = row.region,
    n.description   = row.description,
    n.source_url    = row.source_url
"""


def _load_historical_events(
    client: Neo4jClient,
    curated_dir: Path,
    *,
    strict: bool = True,
) -> LoadResult:
    """Load HistoricalEvent nodes from historical_events.yaml."""
    path = curated_dir / "historical_events.yaml"
    if not path.exists():
        if strict:
            msg = f"Missing required file: {path}"
            raise FileNotFoundError(msg)
        logger.warning("historical_events_missing", path=str(path))
        return LoadResult("HistoricalEvent", 0, 0, 0)

    with open(path) as f:
        data = yaml.safe_load(f)

    events = data.get("events", [])
    batch: list[dict[str, Any]] = []
    errors: list[str] = []
    skipped = 0

    for i, evt in enumerate(events):
        eid = evt.get("id")
        if not eid or not isinstance(eid, str):
            errors.append(f"event {i}: invalid id={eid!r}")
            skipped += 1
            continue
        name_en = evt.get("name_en")
        if not name_en:
            errors.append(f"event {i}: missing name_en")
            skipped += 1
            continue
        batch.append(
            {
                "id": eid,
                "name_en": name_en,
                "name_ar": evt.get("name_ar"),
                "year_start_ah": evt.get("year_start_ah"),
                "year_end_ah": evt.get("year_end_ah"),
                "year_start_ce": evt.get("year_start_ce"),
                "year_end_ce": evt.get("year_end_ce"),
                "event_type": evt.get("type"),
                "caliphate": evt.get("caliphate"),
                "region": evt.get("region"),
                "description": evt.get("description"),
                "source_url": evt.get("source_url"),
            }
        )

    created = client.execute_write_batch(_EVENT_MERGE, batch) if batch else 0
    merged = len(batch) - created
    logger.info("historical_events_loaded", created=created, merged=merged, skipped=skipped)
    return LoadResult("HistoricalEvent", created, merged, skipped, errors)


# ---------------------------------------------------------------------------
# Location loader
# ---------------------------------------------------------------------------

_LOCATION_MERGE = """\
UNWIND $batch AS row
MERGE (n:Location {id: row.id})
SET n.name_en  = row.name_en,
    n.name_ar  = row.name_ar,
    n.region   = row.region,
    n.lat      = row.lat,
    n.lon      = row.lon
"""


def _load_locations(
    client: Neo4jClient,
    curated_dir: Path,
    *,
    strict: bool = True,
) -> LoadResult:
    """Load Location nodes from locations.yaml if available."""
    path = curated_dir / "locations.yaml"
    if not path.exists():
        if strict:
            logger.warning("locations_file_missing", path=str(path))
        return LoadResult("Location", 0, 0, 0)

    with open(path) as f:
        data = yaml.safe_load(f)

    locations = data.get("locations", [])
    batch: list[dict[str, Any]] = []
    errors: list[str] = []
    skipped = 0

    for i, loc in enumerate(locations):
        lid = loc.get("id")
        if not lid or not isinstance(lid, str):
            errors.append(f"location {i}: invalid id={lid!r}")
            skipped += 1
            continue
        full_id = f"loc:{lid}" if not lid.startswith("loc:") else lid
        batch.append(
            {
                "id": full_id,
                "name_en": loc.get("name_en", ""),
                "name_ar": loc.get("name_ar"),
                "region": loc.get("region"),
                "lat": loc.get("lat"),
                "lon": loc.get("lon"),
            }
        )

    created = client.execute_write_batch(_LOCATION_MERGE, batch) if batch else 0
    merged = len(batch) - created
    logger.info("locations_loaded", created=created, merged=merged, skipped=skipped)
    return LoadResult("Location", created, merged, skipped, errors)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def load_all_nodes(
    client: Neo4jClient,
    staging_dir: Path,
    curated_dir: Path,
    *,
    strict: bool = True,
) -> list[LoadResult]:
    """Load all node types into Neo4j.

    Ensures uniqueness constraints first, then loads each node type
    in dependency order (narrators before chains, hadiths before gradings).
    """
    client.ensure_constraints()
    client.ensure_fulltext_indexes()

    results: list[LoadResult] = []
    results.append(_load_narrators(client, staging_dir, curated_dir, strict=strict))
    results.append(_load_hadiths(client, staging_dir, strict=strict))
    results.append(_load_collections(client, staging_dir, strict=strict))
    results.append(_load_chains(client, staging_dir, strict=strict))
    results.append(_load_gradings(client, staging_dir, strict=strict))
    results.append(_load_historical_events(client, curated_dir, strict=strict))
    results.append(_load_locations(client, curated_dir, strict=strict))

    total_created = sum(r.created for r in results)
    total_errors = sum(len(r.validation_errors) for r in results)
    logger.info(
        "all_nodes_loaded",
        total_created=total_created,
        total_errors=total_errors,
        node_types=len(results),
    )
    return results
