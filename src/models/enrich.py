"""Pydantic result models for Phase 4 enrichment operations."""

from pydantic import BaseModel, ConfigDict

__all__ = [
    "EmbeddingLoadResult",
    "EnrichSummary",
    "HistoricalResult",
    "MetricsResult",
    "RecallCheck",
    "RecallVerificationResult",
    "ReindexEmbeddingsResult",
    "TopicResult",
]


class EmbeddingLoadResult(BaseModel):
    """Result of the semantic-search embedding load (hadith vectors → pgvector)."""

    model_config = ConfigDict(frozen=True)

    hadiths_loaded: int
    embeddings_loaded: int
    skipped_empty: int
    model_name: str
    dim: int


class ReindexEmbeddingsResult(BaseModel):
    """Result of rebuilding the ivfflat index after a bulk embedding load (#1057)."""

    model_config = ConfigDict(frozen=True)

    lists: int
    index_name: str


class RecallCheck(BaseModel):
    """Per-query outcome of the semantic-search recall smoke check (#1088)."""

    model_config = ConfigDict(frozen=True)

    query: str
    hits: int
    top_score: float
    keyword_matched: bool
    passed: bool


class RecallVerificationResult(BaseModel):
    """Aggregate recall-verification outcome — the deploy workflow's gate (#1088).

    ``passed`` is the single signal the ``isnad verify-recall`` CLI turns into its
    exit code: structural health (every embeddable hadith has a vector, table is
    populated) AND every per-query topical check passing.
    """

    model_config = ConfigDict(frozen=True)

    embeddings_count: int
    embeddable_count: int
    structural_ok: bool
    checks: list[RecallCheck]
    passed: bool


class MetricsResult(BaseModel):
    """Result of graph metrics computation via Neo4j GDS."""

    model_config = ConfigDict(frozen=True)

    narrators_enriched: int
    betweenness_computed: bool
    pagerank_computed: bool
    louvain_computed: bool
    degree_computed: bool
    communities_found: int


class HistoricalResult(BaseModel):
    """Result of historical overlay (ACTIVE_DURING edge creation)."""

    model_config = ConfigDict(frozen=True)

    edges_created: int
    narrators_linked: int
    compilers_linked: int = 0
    events_linked: int
    narrators_skipped_no_dates: int
    narrators_skipped_max_lifetime: int
    narrators_dated: int = 0
    """Narrator nodes that had resolved date props written this run (ig#1039)."""


class TopicResult(BaseModel):
    """Result of zero-shot topic classification on hadith matn text."""

    model_config = ConfigDict(frozen=True)

    hadiths_classified: int
    hadiths_skipped: int
    model_name: str
    labels_used: list[str]


class EnrichSummary(BaseModel):
    """Aggregated result of the full enrichment pipeline."""

    model_config = ConfigDict(frozen=True)

    metrics: MetricsResult | None
    topics: TopicResult | None
    historical: HistoricalResult | None
    steps_completed: list[str]
    steps_failed: list[str]
