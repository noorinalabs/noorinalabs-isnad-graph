"""Narrator disambiguation via multi-stage matching.

5-stage pipeline: exact → fuzzy (rapidfuzz) → temporal → geographic → cross-ref.
Produces canonical narrator records with deterministic UUID5 IDs,
an ambiguous-narrators report, and a merge audit log.
"""

from __future__ import annotations

import csv
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from src.parse.base import safe_str, write_parquet
from src.resolve.schemas import AMBIGUOUS_NARRATORS_SCHEMA, NARRATORS_CANONICAL_SCHEMA
from src.utils.arabic import normalize_arabic
from src.utils.logging import get_logger

logger = get_logger(__name__)

__all__ = ["run"]

# ---------------------------------------------------------------------------
# Fixed namespace for deterministic canonical IDs
# ---------------------------------------------------------------------------
_CANONICAL_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
_FUZZY_RATIO_THRESHOLD = 80
_LEVENSHTEIN_MAX_DIST = 2
_CONFIDENCE_THRESHOLD = 0.70
_TEMPORAL_MIN_GAP = 15
_TEMPORAL_MAX_GAP = 80


# ---------------------------------------------------------------------------
# Helper dataclasses
# ---------------------------------------------------------------------------
@dataclass
class Candidate:
    """A known narrator from biographical sources."""

    bio_id: str
    name_ar: str | None = None
    name_en: str | None = None
    name_ar_normalized: str | None = None
    kunya: str | None = None
    nisba: str | None = None
    birth_year_ah: int | None = None
    death_year_ah: int | None = None
    birth_location: str | None = None
    death_location: str | None = None
    generation: str | None = None
    gender: str | None = None
    trustworthiness: str | None = None
    external_id: str | None = None
    source: str | None = None


@dataclass
class Match:
    """A disambiguation match between a mention and a candidate."""

    candidate: Candidate
    stage: str
    score: float


@dataclass
class ChainContext:
    """Contextual information about a narrator mention's chain."""

    hadith_id: str
    position_in_chain: int
    source_corpus: str
    adjacent_death_years: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 1: Exact match
# ---------------------------------------------------------------------------
def _exact_match(mention_norm: str, candidates: list[Candidate]) -> list[Match]:
    """Full normalized-name match.

    ``mention_norm`` must already be Arabic-normalized by the caller.
    """
    results: list[Match] = []
    if not mention_norm:
        return results
    for c in candidates:
        if c.name_ar_normalized and c.name_ar_normalized == mention_norm:
            results.append(Match(candidate=c, stage="exact", score=1.0))
        elif c.name_en and c.name_en.strip().lower() == mention_norm.lower():
            results.append(Match(candidate=c, stage="exact", score=1.0))
    return results


# ---------------------------------------------------------------------------
# Stage 2: Fuzzy match
# ---------------------------------------------------------------------------
def _fuzzy_match(mention_norm: str, candidates: list[Candidate]) -> list[Match]:
    """rapidfuzz ratio >= threshold AND Levenshtein distance <= max.

    ``mention_norm`` must already be Arabic-normalized by the caller.
    """
    results: list[Match] = []
    if not mention_norm:
        return results
    for c in candidates:
        cand_name = c.name_ar_normalized or ""
        if not cand_name:
            continue
        ratio = fuzz.ratio(mention_norm, cand_name)
        dist = Levenshtein.distance(mention_norm, cand_name)
        if ratio >= _FUZZY_RATIO_THRESHOLD and dist <= _LEVENSHTEIN_MAX_DIST:
            results.append(
                Match(candidate=c, stage="fuzzy", score=round(ratio / 100.0, 4))
            )
    return results


# ---------------------------------------------------------------------------
# Stage 3: Temporal filter
# ---------------------------------------------------------------------------
def _temporal_filter(
    matches: list[Match], chain_context: ChainContext
) -> list[Match]:
    """Filter matches by plausible teacher-student temporal gap.

    If both the candidate and adjacent narrators in the chain have
    birth/death years, verify the gap falls within 15-80 years.
    Passes through matches when temporal data is missing.
    """
    if not chain_context.adjacent_death_years:
        return matches

    filtered: list[Match] = []
    for m in matches:
        death_year = m.candidate.death_year_ah
        if death_year is None:
            # No temporal data — keep the match (soft constraint).
            filtered.append(m)
            continue
        plausible = False
        for adj_year in chain_context.adjacent_death_years:
            gap = abs(death_year - adj_year)
            if _TEMPORAL_MIN_GAP <= gap <= _TEMPORAL_MAX_GAP:
                plausible = True
                break
        if plausible:
            filtered.append(m)

    return filtered


# ---------------------------------------------------------------------------
# Stage 4: Geographic filter
# ---------------------------------------------------------------------------
def _geographic_filter(matches: list[Match]) -> list[Match]:
    """Soft geographic constraint — pass-through until location ontology exists.

    Geographic filtering is deferred because:
    - No normalized location ontology exists yet (birth/death locations are
      free-text strings with inconsistent transliteration across corpora).
    - Effective filtering requires a curated mapping of historical Islamic
      cities/regions plus known scholarly travel routes.
    - Incorrect filtering would silently drop valid matches, so conservative
      pass-through is preferable until location data is reliable.

    TODO(phase4): Implement geographic filtering once a location ontology
    is built in the enrich stage. Key steps:
      1. Normalize location strings to canonical city/region IDs.
      2. Build a travel-plausibility graph (e.g., Basra<->Baghdad: likely).
      3. Filter candidates whose locations are implausible given chain context.
    """
    return matches


# ---------------------------------------------------------------------------
# Stage 5: Cross-reference match
# ---------------------------------------------------------------------------
def _crossref_match(mention_norm: str, candidates: list[Candidate]) -> list[Match]:
    """Match via external IDs (e.g., muslimscholars.info).

    ``mention_norm`` must already be Arabic-normalized by the caller.
    """
    results: list[Match] = []
    if not mention_norm:
        return results
    for c in candidates:
        if c.external_id and c.name_ar_normalized:
            # If the candidate has an external ID and name is a partial match,
            # boost confidence via cross-reference.
            ratio = fuzz.ratio(mention_norm, c.name_ar_normalized)
            if ratio >= 60:
                results.append(
                    Match(candidate=c, stage="crossref", score=round(ratio / 100.0, 4))
                )
    return results


# ---------------------------------------------------------------------------
# Candidate loading
# ---------------------------------------------------------------------------
def _load_candidates(staging_dir: Path) -> list[Candidate]:
    """Build candidate list from all narrators_bio_*.parquet files."""
    bio_files = sorted(staging_dir.glob("narrators_bio_*.parquet"))
    candidates: list[Candidate] = []

    for bf in bio_files:
        table = pq.read_table(bf)
        for i in range(table.num_rows):
            name_ar = safe_str(table.column("name_ar")[i].as_py())
            name_ar_norm = safe_str(table.column("name_ar_normalized")[i].as_py())
            if not name_ar_norm and name_ar:
                name_ar_norm = normalize_arabic(name_ar)

            candidates.append(
                Candidate(
                    bio_id=table.column("bio_id")[i].as_py(),
                    name_ar=name_ar,
                    name_en=safe_str(table.column("name_en")[i].as_py()),
                    name_ar_normalized=name_ar_norm,
                    kunya=safe_str(table.column("kunya")[i].as_py()),
                    nisba=safe_str(table.column("nisba")[i].as_py()),
                    birth_year_ah=table.column("birth_year_ah")[i].as_py(),
                    death_year_ah=table.column("death_year_ah")[i].as_py(),
                    birth_location=safe_str(table.column("birth_location")[i].as_py()),
                    death_location=safe_str(table.column("death_location")[i].as_py()),
                    generation=safe_str(table.column("generation")[i].as_py()),
                    gender=safe_str(table.column("gender")[i].as_py()),
                    trustworthiness=safe_str(table.column("trustworthiness")[i].as_py()),
                    external_id=safe_str(table.column("external_id")[i].as_py()),
                    source=safe_str(table.column("source")[i].as_py()),
                )
            )

    logger.info(
        "candidates_loaded",
        bio_files=len(bio_files),
        total_candidates=len(candidates),
    )
    return candidates


def _load_mentions(
    staging_dir: Path,
) -> list[dict[str, str | int | float | None]]:
    """Load narrator_mentions_resolved.parquet from NER stage."""
    path = staging_dir / "narrator_mentions_resolved.parquet"
    if not path.exists():
        logger.warning("mentions_file_missing", path=str(path))
        return []

    table = pq.read_table(path)
    rows: list[dict[str, str | int | float | None]] = []
    for i in range(table.num_rows):
        rows.append(
            {
                "mention_id": table.column("mention_id")[i].as_py(),
                "hadith_id": table.column("hadith_id")[i].as_py(),
                "source_corpus": table.column("source_corpus")[i].as_py(),
                "position_in_chain": table.column("position_in_chain")[i].as_py(),
                "name_raw": safe_str(table.column("name_raw")[i].as_py()),
                "name_normalized": safe_str(table.column("name_normalized")[i].as_py()),
                "transmission_method": safe_str(
                    table.column("transmission_method")[i].as_py()
                ),
            }
        )
    logger.info("mentions_loaded", total=len(rows))
    return rows


# ---------------------------------------------------------------------------
# Canonical ID generation
# ---------------------------------------------------------------------------
def _make_canonical_id(name_normalized: str) -> str:
    """Deterministic canonical ID via uuid5 with fixed namespace."""
    return str(uuid.uuid5(_CANONICAL_NAMESPACE, name_normalized))


# ---------------------------------------------------------------------------
# Core disambiguation logic
# ---------------------------------------------------------------------------
def _disambiguate_mention(
    mention: dict[str, str | int | float | None],
    candidates: list[Candidate],
    death_year_index: dict[str, int | None],
) -> tuple[Match | None, list[Match]]:
    """Run 5-stage pipeline on a single mention. Return (best_match, all_matches)."""
    raw_name = str(mention.get("name_normalized") or mention.get("name_raw") or "")
    if not raw_name:
        return None, []

    # Normalize Arabic once; all stages receive the pre-normalized form.
    name = normalize_arabic(raw_name) if raw_name else ""
    if not name:
        return None, []

    # Build chain context for temporal filtering.
    hadith_id = str(mention.get("hadith_id", ""))
    position = int(mention.get("position_in_chain") or 0)
    source_corpus = str(mention.get("source_corpus", ""))

    adjacent_years: list[int] = []
    # Look up adjacent narrators' death years from the index if available.
    for offset in (-1, 1):
        key = f"{hadith_id}:{position + offset}"
        year = death_year_index.get(key)
        if year is not None:
            adjacent_years.append(year)

    chain_ctx = ChainContext(
        hadith_id=hadith_id,
        position_in_chain=position,
        source_corpus=source_corpus,
        adjacent_death_years=adjacent_years,
    )

    all_matches: list[Match] = []

    # Stage 1: Exact match
    exact = _exact_match(name, candidates)
    if exact:
        all_matches.extend(exact)
        return exact[0], all_matches

    # Stage 2: Fuzzy match
    fuzzy = _fuzzy_match(name, candidates)
    if fuzzy:
        # Stage 3: Temporal filter
        fuzzy = _temporal_filter(fuzzy, chain_ctx)
        # Stage 4: Geographic filter
        fuzzy = _geographic_filter(fuzzy)
        all_matches.extend(fuzzy)
        if fuzzy:
            best = max(fuzzy, key=lambda m: m.score)
            return best, all_matches

    # Stage 5: Cross-reference match
    crossref = _crossref_match(name, candidates)
    if crossref:
        all_matches.extend(crossref)
        best = max(crossref, key=lambda m: m.score)
        return best, all_matches

    return None, all_matches


# ---------------------------------------------------------------------------
# Output builders
# ---------------------------------------------------------------------------
def _build_canonical_table(
    canonical_map: dict[str, dict[str, str | int | list[str] | None]],
) -> pa.Table:
    """Build narrators_canonical Parquet table."""
    rows = list(canonical_map.values())
    if not rows:
        return pa.table(
            {f.name: pa.array([], type=f.type) for f in NARRATORS_CANONICAL_SCHEMA},
            schema=NARRATORS_CANONICAL_SCHEMA,
        )

    arrays: dict[str, pa.Array] = {
        "canonical_id": pa.array([r["canonical_id"] for r in rows], type=pa.string()),
        "name_ar": pa.array([r.get("name_ar") for r in rows], type=pa.string()),
        "name_en": pa.array([r.get("name_en") for r in rows], type=pa.string()),
        "name_ar_normalized": pa.array(
            [r.get("name_ar_normalized") for r in rows], type=pa.string()
        ),
        "aliases": pa.array(
            [r.get("aliases") or [] for r in rows], type=pa.list_(pa.string())
        ),
        "birth_year_ah": pa.array(
            [r.get("birth_year_ah") for r in rows], type=pa.int32()
        ),
        "death_year_ah": pa.array(
            [r.get("death_year_ah") for r in rows], type=pa.int32()
        ),
        "generation": pa.array([r.get("generation") for r in rows], type=pa.string()),
        "gender": pa.array([r.get("gender") for r in rows], type=pa.string()),
        "trustworthiness": pa.array(
            [r.get("trustworthiness") for r in rows], type=pa.string()
        ),
        "source_ids": pa.array(
            [r.get("source_ids") or [] for r in rows], type=pa.list_(pa.string())
        ),
        "external_id": pa.array(
            [r.get("external_id") for r in rows], type=pa.string()
        ),
        "mention_count": pa.array(
            [r.get("mention_count", 0) for r in rows], type=pa.int32()
        ),
    }
    return pa.table(arrays, schema=NARRATORS_CANONICAL_SCHEMA)


def _build_ambiguous_csv(
    ambiguous_rows: list[dict[str, str | float | None]],
    output_path: Path,
) -> None:
    """Write ambiguous_narrators.csv."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [f.name for f in AMBIGUOUS_NARRATORS_SCHEMA]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in ambiguous_rows:
            writer.writerow(row)


# ---------------------------------------------------------------------------
# Merge log schema
# ---------------------------------------------------------------------------
_MERGE_LOG_SCHEMA = pa.schema(
    [
        pa.field("canonical_id", pa.string(), nullable=False),
        pa.field("mention_id", pa.string(), nullable=False),
        pa.field("mention_text", pa.string(), nullable=True),
        pa.field("merge_stage", pa.string(), nullable=False),
        pa.field("score", pa.float32(), nullable=False),
    ]
)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def run(staging_dir: Path, output_dir: Path) -> list[Path]:
    """Disambiguate narrator mentions to canonical narrator records.

    Multi-stage pipeline: exact match, fuzzy match, temporal filter,
    geographic filter, cross-reference match.
    """
    logger.info(
        "disambiguate_run_start",
        staging_dir=str(staging_dir),
        output_dir=str(output_dir),
    )

    # Load inputs.
    candidates = _load_candidates(staging_dir)
    mentions = _load_mentions(staging_dir)

    if not mentions:
        logger.warning("disambiguate_no_mentions")
        return []

    if not candidates:
        logger.warning("disambiguate_no_candidates")
        return []

    # Build death-year index for temporal filtering:
    # key = "hadith_id:position" → death_year_ah of the resolved candidate.
    # We populate this incrementally as we resolve mentions.
    death_year_index: dict[str, int | None] = {}

    # Canonical narrator accumulator: normalized_name → metadata dict.
    canonical_map: dict[str, dict[str, str | int | list[str] | None]] = {}
    merge_log_rows: list[dict[str, str | float | None]] = []
    ambiguous_rows: list[dict[str, str | float | None]] = []

    # Per-source counters.
    source_resolved: dict[str, int] = {}
    source_total: dict[str, int] = {}

    for mention in mentions:
        corpus = str(mention.get("source_corpus", "unknown"))
        source_total[corpus] = source_total.get(corpus, 0) + 1

        best, all_matches = _disambiguate_mention(
            mention, candidates, death_year_index
        )

        mention_id = str(mention.get("mention_id", ""))
        mention_text = str(
            mention.get("name_normalized") or mention.get("name_raw") or ""
        )

        if best and best.score >= _CONFIDENCE_THRESHOLD:
            # Resolved.
            source_resolved[corpus] = source_resolved.get(corpus, 0) + 1
            c = best.candidate
            norm_name = c.name_ar_normalized or normalize_arabic(c.name_ar or "")
            canonical_id = _make_canonical_id(norm_name)

            # Update death-year index for temporal chain context.
            hadith_id = str(mention.get("hadith_id", ""))
            position = int(mention.get("position_in_chain") or 0)
            death_year_index[f"{hadith_id}:{position}"] = c.death_year_ah

            # Upsert canonical record.
            if canonical_id not in canonical_map:
                canonical_map[canonical_id] = {
                    "canonical_id": canonical_id,
                    "name_ar": c.name_ar,
                    "name_en": c.name_en,
                    "name_ar_normalized": norm_name,
                    "aliases": [],
                    "birth_year_ah": c.birth_year_ah,
                    "death_year_ah": c.death_year_ah,
                    "generation": c.generation,
                    "gender": c.gender,
                    "trustworthiness": c.trustworthiness,
                    "source_ids": [c.bio_id],
                    "external_id": c.external_id,
                    "mention_count": 1,
                }
            else:
                rec = canonical_map[canonical_id]
                raw_count = rec.get("mention_count")
                prev = int(raw_count) if isinstance(raw_count, (int, str)) else 0
                rec["mention_count"] = prev + 1
                # Merge source IDs.
                src_ids = rec.get("source_ids")
                if isinstance(src_ids, list) and c.bio_id not in src_ids:
                    src_ids.append(c.bio_id)
                # Add alias if different from primary.
                if mention_text and mention_text != norm_name:
                    aliases = rec.get("aliases")
                    if isinstance(aliases, list) and mention_text not in aliases:
                        aliases.append(mention_text)

            # Merge log entry.
            merge_log_rows.append(
                {
                    "canonical_id": canonical_id,
                    "mention_id": mention_id,
                    "mention_text": mention_text,
                    "merge_stage": best.stage,
                    "score": best.score,
                }
            )
        else:
            # Ambiguous — collect top-3 candidates.
            top3 = sorted(all_matches, key=lambda m: m.score, reverse=True)[:3]
            row: dict[str, str | float | None] = {
                "mention_id": mention_id,
                "mention_text": mention_text,
                "source_corpus": corpus,
            }
            for idx in range(3):
                n = idx + 1
                if idx < len(top3):
                    m = top3[idx]
                    norm = m.candidate.name_ar_normalized or ""
                    row[f"candidate_{n}_id"] = _make_canonical_id(norm)
                    row[f"candidate_{n}_name"] = (
                        m.candidate.name_ar or m.candidate.name_en or ""
                    )
                    row[f"candidate_{n}_score"] = m.score
                    row[f"candidate_{n}_stage"] = m.stage
                else:
                    row[f"candidate_{n}_id"] = None
                    row[f"candidate_{n}_name"] = None
                    row[f"candidate_{n}_score"] = None
                    row[f"candidate_{n}_stage"] = None
            ambiguous_rows.append(row)

    # ---------------------------------------------------------------------------
    # Metrics
    # ---------------------------------------------------------------------------
    total_mentions = len(mentions)
    total_resolved = sum(source_resolved.values())
    total_canonical = len(canonical_map)
    total_ambiguous = len(ambiguous_rows)

    for corpus in sorted(source_total):
        resolved = source_resolved.get(corpus, 0)
        total = source_total[corpus]
        rate = round(resolved / total * 100, 1) if total else 0.0
        logger.info(
            "disambiguate_source_rate",
            source_corpus=corpus,
            resolved=resolved,
            total=total,
            rate_pct=rate,
        )

    # Bio coverage: fraction of candidates that got at least one mention match.
    matched_bios = {
        r["canonical_id"]
        for r in merge_log_rows
        if r.get("canonical_id")
    }
    bio_coverage = round(len(matched_bios) / max(len(candidates), 1) * 100, 1)

    logger.info(
        "disambiguate_summary",
        total_mentions=total_mentions,
        total_resolved=total_resolved,
        total_canonical=total_canonical,
        total_ambiguous=total_ambiguous,
        resolution_rate_pct=round(total_resolved / max(total_mentions, 1) * 100, 1),
        bio_coverage_pct=bio_coverage,
    )

    # ---------------------------------------------------------------------------
    # Write outputs
    # ---------------------------------------------------------------------------
    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths: list[Path] = []

    # 1. narrators_canonical.parquet
    canonical_table = _build_canonical_table(canonical_map)
    canonical_path = output_dir / "narrators_canonical.parquet"
    write_parquet(canonical_table, canonical_path, schema=NARRATORS_CANONICAL_SCHEMA)
    output_paths.append(canonical_path)

    # 2. ambiguous_narrators.csv
    if ambiguous_rows:
        ambiguous_path = output_dir / "ambiguous_narrators.csv"
        _build_ambiguous_csv(ambiguous_rows, ambiguous_path)
        output_paths.append(ambiguous_path)

    # 3. merge_log.parquet
    if merge_log_rows:
        log_arrays: dict[str, pa.Array] = {
            "canonical_id": pa.array(
                [r["canonical_id"] for r in merge_log_rows], type=pa.string()
            ),
            "mention_id": pa.array(
                [r["mention_id"] for r in merge_log_rows], type=pa.string()
            ),
            "mention_text": pa.array(
                [r["mention_text"] for r in merge_log_rows], type=pa.string()
            ),
            "merge_stage": pa.array(
                [r["merge_stage"] for r in merge_log_rows], type=pa.string()
            ),
            "score": pa.array(
                [r["score"] for r in merge_log_rows], type=pa.float32()
            ),
        }
        log_table = pa.table(log_arrays, schema=_MERGE_LOG_SCHEMA)
        log_path = output_dir / "merge_log.parquet"
        write_parquet(log_table, log_path, schema=_MERGE_LOG_SCHEMA)
        output_paths.append(log_path)

    logger.info(
        "disambiguate_run_complete",
        output_files=[str(p) for p in output_paths],
    )
    return output_paths
