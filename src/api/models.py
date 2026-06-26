"""API response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PaginatedResponse[T](BaseModel):
    """Generic paginated response wrapper."""

    model_config = ConfigDict(frozen=True)

    items: list[T]
    total: int
    page: int
    limit: int


class NarratorResponse(BaseModel):
    """Narrator API response."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "narrator:bukhari:az-zuhri",
                    "name_ar": "محمد بن مسلم بن شهاب الزهري",
                    "name_en": "Ibn Shihab al-Zuhri",
                    "kunya": "Abu Bakr",
                    "nisba": "al-Zuhri",
                    "laqab": None,
                    "birth_year_ah": 51,
                    "death_year_ah": 124,
                    "generation": "tabi_tabiin",
                    "gender": "male",
                    "sect_affiliation": "sunni",
                    "trustworthiness_consensus": "thiqa",
                    "aliases": ["الزهري", "ابن شهاب"],
                    "betweenness_centrality": 0.042,
                    "in_degree": 87,
                    "out_degree": 134,
                    "pagerank": 0.0031,
                    "community_id": 3,
                }
            ]
        },
    )

    id: str
    name_ar: str
    # name_en and the structured biographical fields below are sparse on real
    # loaded data (most narrators lack an English transliteration, generation,
    # gender, sect, or a trustworthiness grade). They are optional so a node
    # missing them serializes cleanly instead of raising a Pydantic
    # ValidationError → HTTP 500 on GET /narrators (#1024).
    name_en: str | None = None
    kunya: str | None = None
    nisba: str | None = None
    laqab: str | None = None
    birth_year_ah: int | None = None
    death_year_ah: int | None = None
    generation: str | None = None
    gender: str | None = None
    sect_affiliation: str | None = None
    trustworthiness_consensus: str | None = None
    aliases: list[str] = []
    betweenness_centrality: float | None = None
    in_degree: int | None = None
    out_degree: int | None = None
    pagerank: float | None = None
    community_id: int | None = None


class HadithResponse(BaseModel):
    """Hadith API response."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "hadith:bukhari:1",
                    "matn_ar": "إنما الأعمال بالنيات",
                    "matn_en": "Actions are judged by intentions.",
                    "isnad_raw_ar": "حدثنا الحميدي...",
                    "isnad_raw_en": None,
                    "grade_composite": "Sahih - Authentic",
                    "grade_normalized": "sahih",
                    "topic_tags": ["intentions", "sincerity"],
                    "source_corpus": "bukhari",
                    "has_shia_parallel": True,
                    "has_sunni_parallel": True,
                }
            ]
        },
    )

    id: str
    matn_ar: str
    matn_en: str | None = None
    isnad_raw_ar: str | None = None
    isnad_raw_en: str | None = None
    grade_composite: str | None = None
    grade_normalized: str | None = None
    topic_tags: list[str] = []
    source_corpus: str
    collection_name: str | None = None
    display_title: str | None = None
    has_shia_parallel: bool = False
    has_sunni_parallel: bool = False


class TopicFacet(BaseModel):
    """A canonical topic facet bucket with its document count.

    ``value`` is the canonical token (see ``src.utils.topics.TOPIC_LABELS``) or
    ``"uncategorized"`` for hadiths whose tags map to no canonical topic.
    """

    model_config = ConfigDict(frozen=True)

    value: str
    label: str
    count: int


class HadithFacetsResponse(BaseModel):
    """Distinct facet values available for filtering hadiths."""

    model_config = ConfigDict(frozen=True)

    source_corpus: list[str]
    grades: list[str] = []
    # Canonical topic vocabulary with per-bucket document counts, including the
    # ``uncategorized`` bucket. The full vocabulary is always present so the
    # facet is stable regardless of how sparse ``topic_tags`` are (#1061).
    topics: list[TopicFacet] = []


class CollectionResponse(BaseModel):
    """Collection API response."""

    model_config = ConfigDict(frozen=True)

    id: str
    name_ar: str
    name_en: str
    compiler_name: str | None = None
    compiler_id: str | None = None
    compilation_year_ah: int | None = None
    sect: str
    canonical_rank: int | None = None
    total_hadiths: int | None = None
    book_count: int | None = None


class ServiceStatus(BaseModel):
    """Status of an individual service dependency."""

    model_config = ConfigDict(frozen=True)

    status: str
    latency_ms: float | None = None
    version: str | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Comprehensive health check response."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "status": "healthy",
                    "services": {
                        "neo4j": {"status": "up", "latency_ms": 12.3, "version": "5.x"},
                        "postgres": {"status": "up", "latency_ms": 5.1, "version": "16.x"},
                        "redis": {"status": "up", "latency_ms": 1.2},
                    },
                }
            ]
        },
    )

    status: str
    services: dict[str, ServiceStatus]


class StatusResponse(BaseModel):
    """Public-facing status summary."""

    model_config = ConfigDict(frozen=True)

    status: str
    message: str


# --- Graph visualization models ---


class GraphNode(BaseModel):
    """A node in graph visualization data."""

    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    name_ar: str
    name_en: str | None = None
    type: str
    generation: str | None = None
    community_id: int | None = None
    in_degree: int | None = None
    out_degree: int | None = None
    betweenness_centrality: float | None = None
    pagerank: float | None = None
    sect_affiliation: str | None = None
    trustworthiness_consensus: str | None = None
    death_year_ah: int | None = None
    birth_year_ah: int | None = None
    kunya: str | None = None
    nisba: str | None = None


class GraphEdge(BaseModel):
    """An edge in graph visualization data."""

    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    relationship: str
    weight: int = 1
    # Ordinal position of this edge within a single hadith's isnad chain
    # (from the TRANSMITTED_TO.position_in_chain edge property). Only set by
    # the per-hadith chain endpoint; None for network/aggregate edges.
    position: int | None = None


class ChainSummary(BaseModel):
    """Summary of a chain passing through a narrator."""

    model_config = ConfigDict(frozen=True)

    chain_id: str
    hadith_id: str
    matn_ar: str
    matn_en: str | None = None
    grade: str | None = None


class NarratorChainsResponse(BaseModel):
    """Response for narrator chains endpoint."""

    model_config = ConfigDict(frozen=True)

    narrator_id: str
    chains: list[ChainSummary]
    total: int


class ChainVisualization(BaseModel):
    """Full chain visualization data for D3/vis.js rendering."""

    model_config = ConfigDict(frozen=True)

    hadith_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class NarratorNetworkResponse(BaseModel):
    """Ego network response with nodes and edges."""

    model_config = ConfigDict(frozen=True)

    narrator_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    teachers: int
    students: int


# --- Search models ---


class SearchResult(BaseModel):
    """A single search result.

    Beyond the display fields, results carry the facet metadata the search page
    filters on client-side (collection / grade / century / topic). Each field is
    populated only for the result types it applies to and left null/empty
    otherwise: ``collection`` + ``grade`` + ``topics`` for hadiths, ``century``
    for narrators. ``grade`` is the canonical normalized token (see
    ``src.utils.grades.normalize_grade``), not the raw scholar string. ``topics``
    is the canonical topic tokens the hadith's free-text tags map onto (see
    ``src.utils.topics.canonical_topics_for_tags``); an empty list means
    uncategorized/unknown. (#1036, #1061)
    """

    model_config = ConfigDict(frozen=True)

    id: str
    type: str
    title: str
    title_ar: str
    score: float
    collection: str | None = None
    grade: str | None = None
    century: int | None = None
    topics: list[str] = []


class SearchResultsResponse(BaseModel):
    """Search results response."""

    model_config = ConfigDict(frozen=True)

    results: list[SearchResult]
    total: int
    query: str


# --- Parallels models ---


class ParallelHadithResponse(BaseModel):
    """A parallel hadith with similarity metadata."""

    model_config = ConfigDict(frozen=True)

    id: str
    matn_ar: str
    matn_en: str | None = None
    source_corpus: str
    grade: str | None = None
    similarity_score: float | None = None
    variant_type: str | None = None
    cross_sect: bool = False


class ParallelsResponse(BaseModel):
    """Response for parallels endpoint."""

    model_config = ConfigDict(frozen=True)

    hadith_id: str
    parallels: list[ParallelHadithResponse]
    total: int


class ParallelPair(BaseModel):
    """A pair of parallel hadiths with similarity metadata."""

    model_config = ConfigDict(frozen=True)

    hadith_a_id: str
    hadith_a_corpus: str
    # Human-readable title (e.g. "Sahih al-Bukhari 1:1") and a short matn preview,
    # so the Browse table renders readable rows instead of opaque IDs. (#1037)
    hadith_a_title: str | None = None
    hadith_a_snippet: str | None = None
    hadith_b_id: str
    hadith_b_corpus: str
    hadith_b_title: str | None = None
    hadith_b_snippet: str | None = None
    similarity_score: float | None = None
    variant_type: str | None = None
    cross_sect: bool = False


class ParallelPairsResponse(BaseModel):
    """Paginated list of parallel hadith pairs."""

    model_config = ConfigDict(frozen=True)

    items: list[ParallelPair]
    total: int
    page: int
    limit: int


# --- Timeline models ---


class TimelineEntry(BaseModel):
    """A historical event entry for timeline visualization."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    name_ar: str | None = None
    year_ah: int
    end_year_ah: int | None = None
    event_type: str | None = None
    description: str | None = None
    narrator_count: int = 0


class TimelineResponse(BaseModel):
    """Timeline data response."""

    model_config = ConfigDict(frozen=True)

    entries: list[TimelineEntry]
    total: int


class TimelineRangeResponse(BaseModel):
    """Min/max year range for timeline data."""

    model_config = ConfigDict(frozen=True)

    min_year_ah: int
    max_year_ah: int


# --- Chain validation models ---

# Verdict tiers for the chronological-plausibility check. ``impossible`` is
# reserved for disjoint active windows whose deciding endpoints are *attested*
# (a real death/birth year on each side); ``implausible`` covers disjointness
# that only holds once an assumed-lifespan estimate fills a missing endpoint;
# ``ok`` means the windows overlap or there is too little date data to assert
# anything. This is a flag-for-review aid (owner decision, ig#1040) — NOT an
# auto-quarantine and NOT a public authenticity verdict.
ChainValidationVerdict = Literal["impossible", "implausible", "ok"]


class NarratorWindow(BaseModel):
    """A narrator's resolved [start, end] active window in Hijri years.

    ``estimated`` is True when either endpoint had to be derived from the
    assumed-lifespan span because the corresponding birth/death year is unknown.
    """

    model_config = ConfigDict(frozen=True)

    narrator_id: str
    name_ar: str | None = None
    name_en: str | None = None
    birth_year_ah: int | None = None
    death_year_ah: int | None = None
    window_start_ah: int | None = None
    window_end_ah: int | None = None
    estimated: bool = True


class ChainValidationFlag(BaseModel):
    """One TRANSMITTED_TO (teacher->student) edge with a chronological verdict."""

    model_config = ConfigDict(frozen=True)

    verdict: ChainValidationVerdict
    reason: str
    hadith_id: str | None = None
    position_in_chain: int | None = None
    teacher: NarratorWindow
    student: NarratorWindow
    # Year gap between the two disjoint windows (None when the windows overlap or
    # could not be resolved). A larger gap is a stronger signal.
    gap_years_ah: int | None = None


class ChainValidationResponse(BaseModel):
    """Result of the GET /validate/chains chronological-plausibility scan."""

    model_config = ConfigDict(frozen=True)

    flags: list[ChainValidationFlag]
    # Per-verdict counts across every edge evaluated in this scan (not just the
    # returned page), so callers can track the impossible/implausible totals as a
    # regression signal for the in-flight segmentation fix (da#221).
    summary: dict[str, int]
    scanned: int
    # Edges skipped because neither narrator carried any date — cannot be judged.
    undated: int
    assumed_lifespan_ah: int
    # True when the candidate scan hit its cap, so ``summary``/``flags`` reflect a
    # partial view of the graph rather than every edge.
    truncated: bool = False


# --- Admin models ---


class SystemHealthResponse(BaseModel):
    """System health response with per-service status."""

    model_config = ConfigDict(frozen=True)

    status: str
    neo4j: bool
    postgres: bool
    redis: bool


class CollectionStat(BaseModel):
    """Per-collection hadith count for the corpus-scope breakdown."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    sect: str
    hadith_count: int


class SectStat(BaseModel):
    """Per-sect aggregate of the loaded corpus."""

    model_config = ConfigDict(frozen=True)

    sect: str
    hadith_count: int
    collection_count: int


class ContentStatsResponse(BaseModel):
    """Content statistics for the admin dashboard.

    ``narrator_count`` is the raw ``Narrator`` node count. It currently
    overstates the number of *distinct real narrators* because isnad
    segmentation is incomplete — many nodes are still whole/partial chain
    strings rather than individual narrators (da#158). The frontend labels it
    accordingly; a segmented figure will replace it once da#158 lands.

    ``collections`` / ``sects`` give the corpus *scope* so the totals are not
    read as a complete corpus — the loaded data is the Sunni Kutub al-Sittah
    (plus a Riyad as-Salihin fragment); no Shia collections are loaded yet.
    """

    model_config = ConfigDict(frozen=True)

    hadith_count: int
    narrator_count: int
    collection_count: int
    coverage_pct: float
    collections: list[CollectionStat] = Field(default_factory=list)
    sects: list[SectStat] = Field(default_factory=list)


class PopularNarrator(BaseModel):
    """A popular narrator entry for analytics."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    query_count: int


class UsageAnalyticsResponse(BaseModel):
    """Usage analytics for the admin dashboard."""

    model_config = ConfigDict(frozen=True)

    search_volume: int
    api_call_count: int
    popular_narrators: list[PopularNarrator]


# --- Moderation models ---


class ModerationItemResponse(BaseModel):
    """A flagged content item awaiting moderation."""

    model_config = ConfigDict(frozen=True)

    id: str
    entity_type: str
    entity_id: str
    reason: str
    status: str
    flagged_by: str | None = None
    flagged_at: str
    resolved_by: str | None = None
    resolved_at: str | None = None
    notes: str | None = None


class ModerationFlagRequest(BaseModel):
    """Request body for flagging content."""

    model_config = ConfigDict(frozen=True)

    entity_type: str
    entity_id: str
    reason: str


class ModerationUpdateRequest(BaseModel):
    """Request body for approving/rejecting flagged content."""

    model_config = ConfigDict(frozen=True)

    status: Literal["approved", "rejected", "pending"]
    notes: str | None = None


# --- System report models ---


class PipelineMetrics(BaseModel):
    """Pipeline parse/staging metrics."""

    model_config = ConfigDict(frozen=True)

    total_files: int
    total_rows: int
    files: list[dict[str, object]]


class DisambiguationMetrics(BaseModel):
    """Disambiguation rate metrics per source."""

    model_config = ConfigDict(frozen=True)

    ner_mention_count: int
    canonical_narrator_count: int
    ambiguous_count: int
    resolution_rate_pct: float
    ambiguous_pct: float


class DedupMetrics(BaseModel):
    """Dedup/parallel coverage metrics."""

    model_config = ConfigDict(frozen=True)

    parallel_links_count: int
    parallel_verbatim: int
    parallel_close_paraphrase: int
    parallel_thematic: int
    parallel_cross_sect: int


class GraphValidationMetrics(BaseModel):
    """Graph validation results."""

    model_config = ConfigDict(frozen=True)

    orphan_narrators: int
    orphan_hadiths: int
    chain_integrity_pct: float
    collection_coverage_pct: float


class TopicCoverageMetrics(BaseModel):
    """Topic classification coverage."""

    model_config = ConfigDict(frozen=True)

    total_hadiths: int
    classified_count: int
    coverage_pct: float


class SystemReportResponse(BaseModel):
    """Aggregated system output report."""

    model_config = ConfigDict(frozen=True)

    pipeline: PipelineMetrics | None = None
    disambiguation: DisambiguationMetrics | None = None
    dedup: DedupMetrics | None = None
    graph_validation: GraphValidationMetrics | None = None
    topic_coverage: TopicCoverageMetrics | None = None


# --- System config models ---

FORBIDDEN_CONFIG_KEYS = frozenset(
    {
        "neo4j_password",
        "user_service_url",
        "pg_dsn",
        "sunnah_api_key",
        "kaggle_key",
        "google_client_secret",
        "apple_client_secret",
        "facebook_client_secret",
        "github_client_secret",
    }
)


class SystemConfig(BaseModel):
    """Runtime system configuration (no secrets)."""

    model_config = ConfigDict(frozen=True)

    rate_limit_per_minute: int = 60
    cors_origins: list[str] = ["http://localhost:3000"]
    feature_flags: dict[str, bool] = {}
    max_search_results: int = 100
    max_pagination_limit: int = 100
    # Days of application logs to retain before rotation/deletion. Surfaced in the
    # admin Config panel; the persisted value drives Loki retention (deploy#451).
    log_retention_days: int = Field(default=7, ge=1, le=365)


class SystemConfigUpdate(BaseModel):
    """Partial update for system configuration."""

    rate_limit_per_minute: int | None = None
    cors_origins: list[str] | None = None
    feature_flags: dict[str, bool] | None = None
    max_search_results: int | None = None
    max_pagination_limit: int | None = None
    log_retention_days: int | None = Field(default=None, ge=1, le=365)


class ConfigAuditEntry(BaseModel):
    """A single config audit log entry."""

    model_config = ConfigDict(frozen=True)

    key: str
    old_value: str
    new_value: str
    changed_by: str
    changed_at: str


class ConfigAuditResponse(BaseModel):
    """Paginated config audit log."""

    model_config = ConfigDict(frozen=True)

    entries: list[ConfigAuditEntry]
    total: int
