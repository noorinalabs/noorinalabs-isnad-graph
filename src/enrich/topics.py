"""Zero-shot topic classification for hadith matn text.

Uses facebook/bart-large-mnli for multi-label zero-shot classification,
writing the top-3 topic labels and scores back to HADITH nodes in Neo4j.
Gracefully skips if the ``transformers`` library is not installed.
"""

from __future__ import annotations

import os
from typing import Any

from src.models.enrich import TopicResult
from src.utils.logging import get_logger
from src.utils.neo4j_client import Neo4jClient

__all__ = ["run_topics"]

log = get_logger(__name__)

MODEL_NAME = "facebook/bart-large-mnli"
BATCH_SIZE = 32
MIN_TEXT_LENGTH = 20

TOPIC_LABELS: list[str] = [
    "theology",
    "jurisprudence",
    "eschatology",
    "succession/imamate",
    "ritual/worship",
    "ethics/conduct",
    "history/sira",
    "commerce/trade",
    "warfare/jihad",
    "family_law",
    "food/drink",
    "medicine",
    "dreams/visions",
    "end_times",
]


def _load_pipeline() -> Any | None:
    """Load the zero-shot-classification pipeline, or return None if unavailable."""
    try:
        from transformers import pipeline
    except ImportError:
        log.warning("transformers_not_installed", hint="pip install transformers torch")
        return None

    offline = os.environ.get("HF_HUB_OFFLINE", "0") == "1"
    kwargs: dict[str, Any] = {"model": MODEL_NAME, "device": -1}
    if offline:
        kwargs["local_files_only"] = True
    try:
        classifier: Any = pipeline("zero-shot-classification", **kwargs)
    except Exception as exc:
        log.error("pipeline_load_failed", model=MODEL_NAME, error=str(exc))
        return None

    log.info("pipeline_loaded", model=MODEL_NAME)
    return classifier


def _fetch_hadiths(client: Neo4jClient) -> list[dict[str, Any]]:
    """Read hadith id and English matn from Neo4j."""
    return client.execute_read(
        "MATCH (h:Hadith) WHERE h.matn_en IS NOT NULL RETURN h.id AS id, h.matn_en AS matn_en"
    )


def _write_topics(
    client: Neo4jClient,
    batch: list[dict[str, Any]],
) -> None:
    """Write top-3 topic labels and scores back to HADITH nodes."""
    client.execute_write(
        "UNWIND $batch AS row "
        "MATCH (h:Hadith {id: row.id}) "
        "SET h.topic_1 = row.t1, h.topic_1_score = row.s1, "
        "    h.topic_2 = row.t2, h.topic_2_score = row.s2, "
        "    h.topic_3 = row.t3, h.topic_3_score = row.s3",
        {"batch": batch},
    )


def run_topics(client: Neo4jClient, labels: list[str] | None = None) -> TopicResult:
    """Classify hadiths and write top-3 topics to HADITH nodes.

    Parameters
    ----------
    labels:
        Override topic labels. Defaults to ``settings.topic_labels``.
    """
    if labels is None:
        from src.config import get_settings

        labels = list(get_settings().topic_labels)

    classifier = _load_pipeline()
    if classifier is None:
        return TopicResult(
            hadiths_classified=0,
            hadiths_skipped=0,
            model_name=MODEL_NAME,
            labels_used=labels,
        )

    hadiths = _fetch_hadiths(client)
    log.info("hadiths_fetched", count=len(hadiths))

    classified = 0
    skipped = 0

    for batch_start in range(0, len(hadiths), BATCH_SIZE):
        batch_rows = hadiths[batch_start : batch_start + BATCH_SIZE]

        texts: list[str] = []
        ids: list[str] = []
        for row in batch_rows:
            text = row.get("matn_en", "") or ""
            if len(text) < MIN_TEXT_LENGTH:
                skipped += 1
                continue
            texts.append(text)
            ids.append(row["id"])

        if not texts:
            continue

        try:
            results = classifier(texts, candidate_labels=labels, multi_label=False)
        except Exception as exc:
            log.error(
                "batch_classification_failed",
                batch_offset=batch_start,
                error=str(exc),
            )
            skipped += len(texts)
            continue

        # Single result comes back as a dict, not a list
        if isinstance(results, dict):
            results = [results]

        write_batch: list[dict[str, Any]] = []
        for hadith_id, result in zip(ids, results):
            result_labels = result["labels"]
            scores = result["scores"]
            write_batch.append(
                {
                    "id": hadith_id,
                    "t1": result_labels[0],
                    "s1": round(scores[0], 4),
                    "t2": result_labels[1],
                    "s2": round(scores[1], 4),
                    "t3": result_labels[2],
                    "s3": round(scores[2], 4),
                }
            )

        try:
            _write_topics(client, write_batch)
            classified += len(write_batch)
        except Exception as exc:
            log.error(
                "batch_write_failed",
                batch_offset=batch_start,
                error=str(exc),
            )
            skipped += len(write_batch)
            continue

        total_processed = classified + skipped
        if total_processed % 100 < BATCH_SIZE:
            log.info("topic_progress", classified=classified, skipped=skipped)

    log.info("topic_classification_complete", classified=classified, skipped=skipped)
    return TopicResult(
        hadiths_classified=classified,
        hadiths_skipped=skipped,
        model_name=MODEL_NAME,
        labels_used=labels,
    )
