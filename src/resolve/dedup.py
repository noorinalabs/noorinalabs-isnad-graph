"""Hadith deduplication and parallel detection.

Generates sentence-transformer embeddings for hadith matn texts, builds a FAISS
index, and identifies parallel hadith pairs across collections and sects.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pyarrow as pa
import pyarrow.parquet as pq

from src.models.enums import VariantType
from src.resolve.schemas import PARALLEL_LINKS_SCHEMA
from src.utils.logging import get_logger

if TYPE_CHECKING:
    import faiss as faiss_mod  # type: ignore[import-untyped]
    import numpy as np
    import numpy.typing as npt

logger = get_logger(__name__)

__all__ = ["run", "run_dedup"]

# Source corpora classified by sect
_SUNNI_SOURCES: frozenset[str] = frozenset({"lk", "sanadset", "sunnah", "fawaz", "open_hadith"})
_SHIA_SOURCES: frozenset[str] = frozenset({"thaqalayn"})


def _classify_pair(score: float) -> VariantType:
    """Classify a similarity score into a variant type tier."""
    if score >= 0.90:
        return VariantType.VERBATIM
    if score >= 0.80:
        return VariantType.CLOSE_PARAPHRASE
    return VariantType.THEMATIC


def _is_cross_sect(corpus_a: str, corpus_b: str) -> bool:
    """Return True when hadiths come from different sectarian traditions."""
    a_sunni = corpus_a in _SUNNI_SOURCES
    b_sunni = corpus_b in _SUNNI_SOURCES
    a_shia = corpus_a in _SHIA_SOURCES
    b_shia = corpus_b in _SHIA_SOURCES
    return (a_sunni and b_shia) or (a_shia and b_sunni)


def _load_hadith_texts(
    staging_dir: Path,
) -> tuple[list[str], list[str], list[str]]:
    """Load hadith IDs, English matn texts, and source corpora from staging Parquets.

    Returns (hadith_ids, texts, corpora) with null/empty matn_en rows excluded.
    """
    hadith_files = sorted(staging_dir.glob("**/hadiths_*.parquet"))
    if not hadith_files:
        logger.warning("dedup_no_hadith_files", staging_dir=str(staging_dir))
        return [], [], []

    ids: list[str] = []
    texts: list[str] = []
    corpora: list[str] = []
    skipped = 0
    for fpath in hadith_files:
        table = pq.read_table(fpath, columns=["source_id", "matn_en", "source_corpus"])
        for i in range(table.num_rows):
            matn = table.column("matn_en")[i].as_py()
            if not matn or not matn.strip():
                skipped += 1
                continue
            ids.append(table.column("source_id")[i].as_py())
            texts.append(matn)
            corpora.append(table.column("source_corpus")[i].as_py())

    logger.info(
        "dedup_loaded_hadiths",
        included=len(ids),
        skipped=skipped,
        files=len(hadith_files),
    )
    return ids, texts, corpora


def run_dedup(
    staging_dir: Path,
    *,
    batch_size: int = 256,
    top_k: int = 50,
    threshold: float = 0.70,
    index_type: str = "flat",
) -> Path:
    """Run full hadith deduplication pipeline.

    Parameters
    ----------
    staging_dir:
        Directory containing hadith Parquet files.
    batch_size:
        Batch size for embedding generation.
    top_k:
        Number of nearest neighbors to retrieve per hadith.
    threshold:
        Minimum cosine similarity to keep a pair (>= 0.70).
    index_type:
        FAISS index type -- ``"flat"`` for IndexFlatIP,
        ``"ivf"`` for IndexIVFFlat (better for large datasets).

    Returns
    -------
    Path to the output ``parallel_links.parquet`` file. The file is written
    even when zero pairs are found (empty table matching the schema).
    """
    t0 = time.monotonic()

    # ------------------------------------------------------------------
    # 1. Load hadith texts
    # ------------------------------------------------------------------
    hadith_ids, texts, corpora = _load_hadith_texts(staging_dir)
    if not texts:
        logger.warning("dedup_no_texts")
        return _write_empty_output(staging_dir)

    # ------------------------------------------------------------------
    # 2. Generate embeddings
    # ------------------------------------------------------------------
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.error(
            "dedup_missing_deps",
            msg="sentence-transformers or numpy not installed -- skipping dedup",
        )
        return _write_empty_output(staging_dir)

    logger.info("dedup_loading_model", model="paraphrase-multilingual-MiniLM-L12-v2")
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    logger.info("dedup_encoding", count=len(texts), batch_size=batch_size)

    # Encode in chunks to log progress during embedding generation (#81)
    all_embeddings: list[npt.NDArray[np.float32]] = []
    for start in range(0, len(texts), batch_size):
        end = min(start + batch_size, len(texts))
        chunk: npt.NDArray[np.float32] = model.encode(
            texts[start:end],
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        all_embeddings.append(chunk)
        logger.info("dedup_encoding_progress", processed=end, total=len(texts))

    embeddings: npt.NDArray[np.float32] = np.vstack(all_embeddings)
    # Ensure float32 for FAISS
    embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)

    # ------------------------------------------------------------------
    # 3. Persist embeddings & ID mapping
    # ------------------------------------------------------------------
    np.save(staging_dir / "hadith_embeddings.npy", embeddings)
    with open(staging_dir / "hadith_id_mapping.json", "w") as f:
        json.dump(hadith_ids, f)
    logger.info(
        "dedup_embeddings_saved",
        shape=list(embeddings.shape),
        dir=str(staging_dir),
    )

    # ------------------------------------------------------------------
    # 4. Build FAISS index & search
    # ------------------------------------------------------------------
    try:
        import faiss
    except ImportError:
        logger.error(
            "dedup_missing_faiss",
            msg="faiss-cpu not installed -- skipping similarity search",
        )
        return _write_empty_output(staging_dir)

    dim = embeddings.shape[1]
    faiss_index: faiss_mod.Index
    if index_type == "ivf":
        nlist = min(100, len(texts))
        quantizer = faiss.IndexFlatIP(dim)
        faiss_index = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT)
        faiss_index.train(embeddings)
        faiss_index.nprobe = min(10, nlist)
    else:
        faiss_index = faiss.IndexFlatIP(dim)

    faiss_index.add(embeddings)
    faiss.write_index(faiss_index, str(staging_dir / "hadith_embeddings.faiss"))
    logger.info("dedup_index_built", index_type=index_type, vectors=faiss_index.ntotal)

    # Query in one call -- scores shape (n, top_k)
    actual_k = min(top_k + 1, len(texts))  # +1 to account for self-match
    scores_matrix, indices_matrix = faiss_index.search(embeddings, actual_k)

    # ------------------------------------------------------------------
    # 5. Collect and classify pairs
    # ------------------------------------------------------------------
    id_to_corpus: dict[str, str] = dict(zip(hadith_ids, corpora))
    seen_pairs: set[tuple[str, str]] = set()

    ids_a: list[str] = []
    ids_b: list[str] = []
    sim_scores: list[float] = []
    variant_types: list[str] = []
    cross_sects: list[bool] = []

    for i in range(len(hadith_ids)):
        hid_a = hadith_ids[i]
        for j_idx in range(actual_k):
            neighbor = int(indices_matrix[i, j_idx])
            score = float(scores_matrix[i, j_idx])

            if neighbor < 0 or neighbor == i:
                continue
            if score < threshold:
                continue

            hid_b = hadith_ids[neighbor]

            # Canonical ordering to eliminate symmetric duplicates
            if hid_a >= hid_b:
                pair_key = (hid_b, hid_a)
            else:
                pair_key = (hid_a, hid_b)

            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            ids_a.append(pair_key[0])
            ids_b.append(pair_key[1])
            sim_scores.append(score)
            variant_types.append(str(_classify_pair(score)))
            cross_sects.append(_is_cross_sect(id_to_corpus[pair_key[0]], id_to_corpus[pair_key[1]]))

    # ------------------------------------------------------------------
    # 6. Write output
    # ------------------------------------------------------------------
    table = pa.table(
        {
            "hadith_id_a": pa.array(ids_a, type=pa.string()),
            "hadith_id_b": pa.array(ids_b, type=pa.string()),
            "similarity_score": pa.array(sim_scores, type=pa.float32()),
            "variant_type": pa.array(variant_types, type=pa.string()),
            "cross_sect": pa.array(cross_sects, type=pa.bool_()),
        },
        schema=PARALLEL_LINKS_SCHEMA,
    )

    output_path = staging_dir / "parallel_links.parquet"
    pq.write_table(table, output_path)

    # ------------------------------------------------------------------
    # 7. Summary logging
    # ------------------------------------------------------------------
    elapsed = time.monotonic() - t0
    tier_counts: dict[str, int] = {vt.value: 0 for vt in VariantType}
    cross_sect_count = 0
    for vt, cs in zip(variant_types, cross_sects):
        tier_counts[vt] = tier_counts.get(vt, 0) + 1
        if cs:
            cross_sect_count += 1

    logger.info(
        "dedup_complete",
        total_pairs=len(ids_a),
        verbatim=tier_counts[VariantType.VERBATIM],
        close_paraphrase=tier_counts[VariantType.CLOSE_PARAPHRASE],
        thematic=tier_counts[VariantType.THEMATIC],
        cross_sect=cross_sect_count,
        elapsed_seconds=round(elapsed, 2),
    )
    return output_path


def _write_empty_output(staging_dir: Path) -> Path:
    """Write an empty parallel_links.parquet and return its path."""
    table = PARALLEL_LINKS_SCHEMA.empty_table()
    output_path = staging_dir / "parallel_links.parquet"
    pq.write_table(table, output_path)
    logger.info("dedup_empty_output", path=str(output_path))
    return output_path


def run(staging_dir: Path, output_dir: Path) -> list[Path]:
    """Entry point matching the resolve pipeline interface.

    Delegates to ``run_dedup`` and wraps the result in a list for compatibility
    with the resolve orchestrator.
    """
    path = run_dedup(staging_dir)
    if path.exists():
        return [path]
    return []
