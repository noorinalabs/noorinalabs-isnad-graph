"""Parse the Sanadset Kaggle dataset into staging Parquet files.

The hadith dataset uses XML-style inline tags:
- ``<SANAD>...</SANAD>`` — isnad (chain of narration)
- ``<MATN>...</MATN>`` — matn (hadith text body)
- ``<NAR>...</NAR>`` — narrator name within the SANAD

Produces three Parquet files:
- ``hadiths_sanadset.parquet`` — hadith records
- ``narrator_mentions_sanadset.parquet`` — narrator mentions per chain
- ``narrators_bio_kaggle.parquet`` — narrator biographies from narrators dataset
"""

from __future__ import annotations

import re
from pathlib import Path

import pyarrow as pa

from src.config import get_settings
from src.parse.base import (
    generate_source_id,
    read_csv_robust,
    safe_int,
    safe_str,
    write_parquet,
)
from src.parse.schemas import HADITH_SCHEMA, NARRATOR_BIO_SCHEMA, NARRATOR_MENTION_SCHEMA
from src.utils.arabic import extract_transmission_phrases, normalize_arabic
from src.utils.logging import get_logger

logger = get_logger(__name__)

__all__ = ["parse_sanadset"]

# ---------------------------------------------------------------------------
# Compiled regexes for XML-style tag extraction
# ---------------------------------------------------------------------------

_SANAD_RE: re.Pattern[str] = re.compile(r"<SANAD>(.*?)</SANAD>", re.DOTALL)
_MATN_RE: re.Pattern[str] = re.compile(r"<MATN>(.*?)</MATN>", re.DOTALL)
_NAR_RE: re.Pattern[str] = re.compile(r"<NAR>(.*?)</NAR>", re.DOTALL)

_CHUNK_SIZE = 50_000
_SOURCE_CORPUS = "sanadset"
_BIO_SOURCE = "kaggle_narrators"


def _extract_tag(pattern: re.Pattern[str], text: str) -> str | None:
    """Extract first match of a tag pattern, returning stripped content or None."""
    m = pattern.search(text)
    if m:
        content = m.group(1).strip()
        return content if content else None
    return None


def _extract_narrator_mentions(
    sanad_text: str,
    source_hadith_id: str,
) -> list[dict[str, str | int | None]]:
    """Extract narrator mentions from SANAD text containing NAR tags.

    Returns list of dicts matching NARRATOR_MENTION_SCHEMA fields.
    """
    mentions: list[dict[str, str | int | None]] = []
    nar_matches = list(_NAR_RE.finditer(sanad_text))

    for idx, match in enumerate(nar_matches):
        name_raw = match.group(1).strip()
        if not name_raw:
            continue

        name_ar_normalized = normalize_arabic(name_raw)
        mention_id = generate_source_id(_SOURCE_CORPUS, "mention", source_hadith_id, str(idx))

        # Extract transmission method from text between previous NAR end and current NAR start
        transmission_method: str | None = None
        if idx > 0:
            prev_end = nar_matches[idx - 1].end()
            between_text = sanad_text[prev_end : match.start()]
        else:
            between_text = sanad_text[: match.start()]

        if between_text.strip():
            phrases = extract_transmission_phrases(between_text)
            if phrases:
                transmission_method = phrases[0][2]  # label of first match

        mentions.append({
            "mention_id": mention_id,
            "source_hadith_id": source_hadith_id,
            "source_corpus": _SOURCE_CORPUS,
            "position_in_chain": idx,
            "name_ar": name_raw,
            "name_en": None,
            "name_ar_normalized": name_ar_normalized,
            "transmission_method": transmission_method,
        })

    return mentions


def _process_chunk(
    rows: list[dict[str, object]],
    collection_name: str,
) -> tuple[list[dict[str, object]], list[dict[str, str | int | None]], int]:
    """Process a chunk of rows, returning hadith records, narrator mentions, and malformed count."""
    hadiths: list[dict[str, object]] = []
    mentions: list[dict[str, str | int | None]] = []
    malformed_count = 0

    for row in rows:
        full_text = safe_str(row.get("hadith") or row.get("text") or row.get("Hadith"))
        if full_text is None:
            continue

        hadith_num = safe_int(
            row.get("hadith_id") or row.get("id") or row.get("Hadith_ID")
        )
        book_num = safe_int(row.get("book_id") or row.get("book") or row.get("Book_ID"))

        source_id = generate_source_id(
            _SOURCE_CORPUS,
            collection_name,
            str(book_num or 0),
            str(hadith_num or 0),
        )

        # Extract SANAD and MATN content
        sanad_text = _extract_tag(_SANAD_RE, full_text)
        matn_text = _extract_tag(_MATN_RE, full_text)

        # Handle "No SANAD" rows
        isnad_raw_ar: str | None = None
        if sanad_text and sanad_text.lower() != "no sanad":
            isnad_raw_ar = sanad_text

        hadiths.append({
            "source_id": source_id,
            "source_corpus": _SOURCE_CORPUS,
            "collection_name": collection_name,
            "book_number": book_num,
            "chapter_number": None,
            "hadith_number": hadith_num,
            "matn_ar": matn_text,
            "matn_en": None,
            "isnad_raw_ar": isnad_raw_ar,
            "isnad_raw_en": None,
            "full_text_ar": full_text,
            "full_text_en": None,
            "grade": safe_str(row.get("grade") or row.get("Grade")),
            "chapter_name_ar": safe_str(row.get("chapter") or row.get("Chapter")),
            "chapter_name_en": None,
            "sect": "sunni",
        })

        # Extract narrator mentions from SANAD if available
        if isnad_raw_ar:
            try:
                row_mentions = _extract_narrator_mentions(isnad_raw_ar, source_id)
                mentions.extend(row_mentions)
            except Exception:  # noqa: BLE001
                malformed_count += 1
                logger.debug("malformed_nar_tags", source_id=source_id)

    return hadiths, mentions, malformed_count


def _parse_narrators_bio(narrators_dir: Path) -> pa.Table | None:
    """Parse narrator biography CSV files dynamically based on available headers."""
    csv_files = list(narrators_dir.glob("*.csv"))
    if not csv_files:
        logger.warning("no_narrator_bio_csv", dir=str(narrators_dir))
        return None

    all_bios: list[dict[str, object]] = []

    for csv_file in csv_files:
        table, _enc = read_csv_robust(csv_file)
        column_names = [c.lower() for c in table.column_names]

        # Build a mapping from expected fields to actual column names
        field_map: dict[str, str] = {}
        for actual_name in table.column_names:
            lower = actual_name.lower()
            if lower in ("name", "narrator_name", "name_ar", "narrator"):
                field_map["name_ar"] = actual_name
            elif lower in ("english_name", "name_en", "name_english"):
                field_map["name_en"] = actual_name
            elif lower in ("kunya", "kunyah"):
                field_map["kunya"] = actual_name
            elif lower in ("nisba", "nisbah"):
                field_map["nisba"] = actual_name
            elif lower in ("laqab",):
                field_map["laqab"] = actual_name
            elif lower in ("birth_year", "birth", "birth_year_ah"):
                field_map["birth_year_ah"] = actual_name
            elif lower in ("death_year", "death", "death_year_ah"):
                field_map["death_year_ah"] = actual_name
            elif lower in ("birth_location", "birth_place"):
                field_map["birth_location"] = actual_name
            elif lower in ("death_location", "death_place"):
                field_map["death_location"] = actual_name
            elif lower in ("generation", "tabaqa", "tabaqat"):
                field_map["generation"] = actual_name
            elif lower in ("gender", "sex"):
                field_map["gender"] = actual_name
            elif lower in (
                "trustworthiness",
                "rank",
                "grade",
                "jarh_tadil",
                "reliability",
            ):
                field_map["trustworthiness"] = actual_name
            elif lower in ("bio", "biography", "bio_text", "description"):
                field_map["bio_text"] = actual_name
            elif lower in ("id", "narrator_id", "external_id"):
                field_map["external_id"] = actual_name

        logger.info(
            "narrator_bio_columns",
            file=csv_file.name,
            available=column_names,
            mapped=list(field_map.keys()),
        )

        for i in range(table.num_rows):
            row_dict: dict[str, object] = {
                col: table.column(col)[i].as_py() for col in table.column_names
            }

            name_ar = safe_str(row_dict.get(field_map.get("name_ar", "")))
            ext_id = safe_str(row_dict.get(field_map.get("external_id", "")))
            bio_id = generate_source_id(
                _BIO_SOURCE,
                csv_file.stem,
                str(ext_id or i),
            )
            name_ar_norm = normalize_arabic(name_ar) if name_ar else None

            all_bios.append({
                "bio_id": bio_id,
                "source": _BIO_SOURCE,
                "name_ar": name_ar,
                "name_en": safe_str(row_dict.get(field_map.get("name_en", ""))),
                "name_ar_normalized": name_ar_norm,
                "name_en_normalized": None,
                "kunya": safe_str(row_dict.get(field_map.get("kunya", ""))),
                "nisba": safe_str(row_dict.get(field_map.get("nisba", ""))),
                "laqab": safe_str(row_dict.get(field_map.get("laqab", ""))),
                "birth_year_ah": safe_int(row_dict.get(field_map.get("birth_year_ah", ""))),
                "death_year_ah": safe_int(row_dict.get(field_map.get("death_year_ah", ""))),
                "birth_location": safe_str(
                    row_dict.get(field_map.get("birth_location", ""))
                ),
                "death_location": safe_str(
                    row_dict.get(field_map.get("death_location", ""))
                ),
                "generation": safe_str(row_dict.get(field_map.get("generation", ""))),
                "gender": safe_str(row_dict.get(field_map.get("gender", ""))),
                "trustworthiness": safe_str(
                    row_dict.get(field_map.get("trustworthiness", ""))
                ),
                "bio_text": safe_str(row_dict.get(field_map.get("bio_text", ""))),
                "external_id": str(ext_id) if ext_id else None,
            })

    if not all_bios:
        return None

    return pa.Table.from_pylist(all_bios, schema=NARRATOR_BIO_SCHEMA)


def parse_sanadset(
    raw_dir: Path | None = None,
    staging_dir: Path | None = None,
) -> dict[str, Path]:
    """Parse Sanadset raw CSV files into staging Parquet.

    Parameters
    ----------
    raw_dir
        Directory containing downloaded Sanadset CSV files.
        Defaults to ``{data_raw_dir}/sanadset/``.
    staging_dir
        Output directory for Parquet files.
        Defaults to ``{data_staging_dir}/``.

    Returns
    -------
    dict[str, Path]
        Mapping of output name to Parquet file path.
    """
    settings = get_settings()
    if raw_dir is None:
        raw_dir = settings.data_raw_dir / "sanadset"
    if staging_dir is None:
        staging_dir = settings.data_staging_dir

    staging_dir.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(raw_dir.glob("*.csv"))
    if not csv_files:
        msg = f"No CSV files found in {raw_dir}"
        raise FileNotFoundError(msg)

    all_hadiths: list[dict[str, object]] = []
    all_mentions: list[dict[str, str | int | None]] = []
    total_malformed = 0
    total_rows = 0

    for csv_file in csv_files:
        logger.info("parsing_csv", file=csv_file.name)
        table, _enc = read_csv_robust(csv_file)
        total_rows += table.num_rows

        # Convert to list of dicts and process in chunks
        rows = [
            {col: table.column(col)[i].as_py() for col in table.column_names}
            for i in range(table.num_rows)
        ]

        collection_name = csv_file.stem.lower().replace(" ", "_")

        for chunk_start in range(0, len(rows), _CHUNK_SIZE):
            chunk = rows[chunk_start : chunk_start + _CHUNK_SIZE]
            hadiths, mentions, malformed = _process_chunk(chunk, collection_name)
            all_hadiths.extend(hadiths)
            all_mentions.extend(mentions)
            total_malformed += malformed

            logger.info(
                "chunk_processed",
                file=csv_file.name,
                offset=chunk_start,
                hadiths=len(hadiths),
                mentions=len(mentions),
            )

    # Data quality logging
    valid_sanad_count = sum(1 for h in all_hadiths if h["isnad_raw_ar"] is not None)
    valid_sanad_pct = (valid_sanad_count / len(all_hadiths) * 100) if all_hadiths else 0
    avg_narrators = (
        len(all_mentions) / valid_sanad_count if valid_sanad_count > 0 else 0
    )

    logger.info(
        "sanadset_parse_quality",
        total_rows=total_rows,
        parsed_hadiths=len(all_hadiths),
        valid_sanad_pct=round(valid_sanad_pct, 1),
        narrator_mentions=len(all_mentions),
        avg_narrators_per_chain=round(avg_narrators, 2),
        malformed_tags=total_malformed,
    )

    # Write hadith Parquet
    outputs: dict[str, Path] = {}

    hadith_table = pa.Table.from_pylist(all_hadiths, schema=HADITH_SCHEMA)
    outputs["hadiths"] = write_parquet(
        hadith_table,
        staging_dir / "hadiths_sanadset.parquet",
        schema=HADITH_SCHEMA,
    )

    # Write narrator mentions Parquet
    if all_mentions:
        mentions_table = pa.Table.from_pylist(all_mentions, schema=NARRATOR_MENTION_SCHEMA)
        outputs["narrator_mentions"] = write_parquet(
            mentions_table,
            staging_dir / "narrator_mentions_sanadset.parquet",
            schema=NARRATOR_MENTION_SCHEMA,
        )

    # Parse and write narrator bios
    narrators_dir = raw_dir / "narrators"
    if narrators_dir.exists():
        bio_table = _parse_narrators_bio(narrators_dir)
        if bio_table is not None:
            outputs["narrators_bio"] = write_parquet(
                bio_table,
                staging_dir / "narrators_bio_kaggle.parquet",
                schema=NARRATOR_BIO_SCHEMA,
            )

    logger.info("sanadset_parse_complete", outputs=list(outputs.keys()))
    return outputs
