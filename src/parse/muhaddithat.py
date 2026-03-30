"""Parse Muhaddithat isnad-datasets into staging Parquet.

Produces two output files:
- narrators_bio_muhaddithat.parquet  (NARRATOR_BIO_SCHEMA)
- network_edges_muhaddithat.parquet  (NETWORK_EDGE_SCHEMA)

The repository contains hadith records with narrator ID sequences and
a narrator table with biographical information.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pcsv

from src.parse.base import (
    safe_str,
    write_parquet,
)
from src.parse.schemas import NARRATOR_BIO_SCHEMA, NETWORK_EDGE_SCHEMA
from src.utils.arabic import normalize_arabic
from src.utils.logging import get_logger

logger = get_logger(__name__)

SOURCE = "muhaddithat"


def _find_csv(base_dir: Path, pattern: str) -> Path:
    """Find the first CSV matching *pattern* (case-insensitive) under *base_dir*."""
    matches = list(base_dir.rglob(pattern))
    if not matches:
        msg = f"No file matching '{pattern}' found under {base_dir}"
        raise FileNotFoundError(msg)
    return matches[0]


def _read_csv(path: Path) -> pa.Table:
    """Read CSV with robust encoding fallback."""
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return pcsv.read_csv(str(path), read_options=pcsv.ReadOptions(encoding=enc))
        except Exception:  # noqa: BLE001
            continue
    msg = f"Failed to read {path} with any encoding"
    raise ValueError(msg)


def _parse_narrator_bios(narrators_path: Path) -> tuple[pa.Table, dict[str, str]]:
    """Parse narrator CSV into NARRATOR_BIO_SCHEMA table.

    Returns (bio_table, id_to_name_map) where id_to_name_map maps
    external_id -> display_name for edge construction.
    """
    table = _read_csv(narrators_path)
    headers = [h.lower().strip() for h in table.column_names]
    header_map = dict(zip(headers, table.column_names, strict=False))

    rows: list[dict[str, str | int | None]] = []
    id_to_name: dict[str, str] = {}
    seen_ids: set[str] = set()

    # Detect column names (the repo may use various conventions).
    id_col = header_map.get("id") or header_map.get("narrator_id")
    name_col = (
        header_map.get("name")
        or header_map.get("displayname")
        or header_map.get("display_name")
        or header_map.get("fullname")
    )
    arabic_name_col = header_map.get("arabicname") or header_map.get("arabic_name")
    gender_col = header_map.get("gender")
    bio_col = header_map.get("bio") or header_map.get("biography")

    # Need at least id + one name column (Arabic or transliterated).
    if not id_col or not (name_col or arabic_name_col):
        msg = f"Required columns (id, name) not found. Headers: {table.column_names}"
        raise ValueError(msg)

    id_values = table.column(id_col).to_pylist()
    name_values = table.column(name_col).to_pylist() if name_col else [None] * table.num_rows
    arabic_name_values = (
        table.column(arabic_name_col).to_pylist() if arabic_name_col else [None] * table.num_rows
    )
    gender_values = table.column(gender_col).to_pylist() if gender_col else [None] * table.num_rows
    bio_values = table.column(bio_col).to_pylist() if bio_col else [None] * table.num_rows

    for i in range(table.num_rows):
        ext_id = safe_str(id_values[i])
        display_name = safe_str(name_values[i])
        arabic_name = safe_str(arabic_name_values[i])
        if not ext_id:
            continue
        if ext_id in seen_ids:
            logger.warning("duplicate_narrator_id", external_id=ext_id, row=i)
            continue
        seen_ids.add(ext_id)

        # Use the dedicated Arabic name column when available; the display
        # name (Latin transliteration) goes into name_en.
        name_ar = arabic_name
        name_en = display_name
        name_ar_norm = normalize_arabic(arabic_name) if arabic_name else None
        name_en_norm = display_name.lower().strip() if display_name else None
        gender = safe_str(gender_values[i])
        bio_text = safe_str(bio_values[i])

        if display_name:
            id_to_name[ext_id] = display_name

        rows.append(
            {
                "bio_id": f"{SOURCE}:{ext_id}",
                "source": SOURCE,
                "name_ar": name_ar,
                "name_en": name_en,
                "name_ar_normalized": name_ar_norm,
                "name_en_normalized": name_en_norm,
                "kunya": None,
                "nisba": None,
                "laqab": None,
                "birth_year_ah": None,
                "death_year_ah": None,
                "birth_location": None,
                "death_location": None,
                "generation": None,
                "gender": gender,
                "trustworthiness": None,
                "bio_text": bio_text,
                "external_id": ext_id,
            }
        )

    if not rows:
        msg = "No valid narrator bios parsed"
        raise ValueError(msg)

    arrays = {field.name: [r[field.name] for r in rows] for field in NARRATOR_BIO_SCHEMA}
    bio_table = pa.table(arrays, schema=NARRATOR_BIO_SCHEMA)

    logger.info("muhaddithat_bios_parsed", unique_narrators=len(rows))
    return bio_table, id_to_name


def _parse_network_edges(
    hadiths_path: Path,
    id_to_name: dict[str, str],
) -> pa.Table:
    """Parse hadith CSV to extract isnad network edges.

    Each hadith row contains a sequence of narrator IDs. Consecutive pairs
    form directed TRANSMITTED_TO edges: narrator[i] -> narrator[i+1].
    """
    table = _read_csv(hadiths_path)
    headers = [h.lower().strip() for h in table.column_names]
    header_map = dict(zip(headers, table.column_names, strict=False))

    # Detect the narrator chain column (comma-separated IDs).
    chain_col = (
        header_map.get("narrator_ids")
        or header_map.get("narrators")
        or header_map.get("chain")
        or header_map.get("isnad")
    )
    hadith_id_col = header_map.get("id") or header_map.get("hadith_id")

    if not chain_col:
        msg = f"No narrator chain column found. Headers: {table.column_names}"
        raise ValueError(msg)

    chain_values = table.column(chain_col).to_pylist()
    hadith_id_values = (
        table.column(hadith_id_col).to_pylist() if hadith_id_col else list(range(table.num_rows))
    )

    edges: list[dict[str, str | None]] = []
    chain_lengths: list[int] = []
    skipped_single = 0

    for i in range(table.num_rows):
        raw_chain = safe_str(chain_values[i])
        if not raw_chain:
            continue

        narrator_ids = [nid.strip() for nid in raw_chain.split(",") if nid.strip()]
        chain_lengths.append(len(narrator_ids))

        if len(narrator_ids) < 2:
            skipped_single += 1
            continue

        h_id = safe_str(hadith_id_values[i])
        hadith_ref = f"{SOURCE}:{h_id}" if h_id else None

        for j in range(len(narrator_ids) - 1):
            from_id = narrator_ids[j]
            to_id = narrator_ids[j + 1]

            if from_id == to_id:
                logger.debug("repeated_narrator_in_chain", hadith=h_id, narrator_id=from_id)
                continue

            from_name = id_to_name.get(from_id, from_id)
            to_name = id_to_name.get(to_id, to_id)

            edges.append(
                {
                    "from_narrator_name": from_name,
                    "to_narrator_name": to_name,
                    "hadith_id": hadith_ref,
                    "source": SOURCE,
                    "from_external_id": from_id,
                    "to_external_id": to_id,
                }
            )

    if not edges:
        msg = "No network edges extracted from hadith chains"
        raise ValueError(msg)

    arrays = {field.name: [e[field.name] for e in edges] for field in NETWORK_EDGE_SCHEMA}
    edge_table = pa.table(arrays, schema=NETWORK_EDGE_SCHEMA)

    # Compute stats.
    unique_narrators = len(
        {e["from_external_id"] for e in edges} | {e["to_external_id"] for e in edges}
    )
    avg_chain = sum(chain_lengths) / len(chain_lengths) if chain_lengths else 0
    bio_narrator_ids = set(id_to_name.keys())
    edge_narrator_ids = {e["from_external_id"] for e in edges} | {
        e["to_external_id"] for e in edges
    }
    matched = len(edge_narrator_ids & bio_narrator_ids)
    match_rate = matched / len(edge_narrator_ids) if edge_narrator_ids else 0

    logger.info(
        "muhaddithat_edges_parsed",
        unique_edges=len(edges),
        unique_narrators=unique_narrators,
        avg_chain_length=round(avg_chain, 2),
        bio_match_rate=round(match_rate, 4),
        skipped_single_chains=skipped_single,
    )

    return edge_table


def run(raw_dir: Path, staging_dir: Path) -> tuple[Path, Path]:
    """Parse Muhaddithat datasets into bio and edge Parquet files."""
    source_dir = raw_dir / "muhaddithat"
    if not source_dir.exists():
        msg = f"Source directory not found: {source_dir}"
        raise FileNotFoundError(msg)

    # Find CSV files.
    hadiths_path = _find_csv(source_dir, "hadiths.csv")

    # Try to find a narrator/scholars CSV.
    narrator_csv_names = ["narrators.csv", "scholars.csv", "narrator*.csv", "*narrator*.csv"]
    narrators_path: Path | None = None
    for pattern in narrator_csv_names:
        matches = list(source_dir.rglob(pattern))
        if matches:
            narrators_path = matches[0]
            break

    if narrators_path is None:
        msg = f"No narrator CSV found under {source_dir}"
        raise FileNotFoundError(msg)

    logger.info(
        "muhaddithat_files_found",
        hadiths=str(hadiths_path),
        narrators=str(narrators_path),
    )

    # Parse bios first (need id->name map for edges).
    bio_table, id_to_name = _parse_narrator_bios(narrators_path)
    bio_path = staging_dir / "narrators_bio_muhaddithat.parquet"
    write_parquet(bio_table, bio_path, schema=NARRATOR_BIO_SCHEMA)

    # Parse edges.
    edge_table = _parse_network_edges(hadiths_path, id_to_name)
    edge_path = staging_dir / "network_edges_muhaddithat.parquet"
    write_parquet(edge_table, edge_path, schema=NETWORK_EDGE_SCHEMA)

    return bio_path, edge_path
