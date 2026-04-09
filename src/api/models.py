"""API response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


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
    name_en: str
    kunya: str | None = None
    nisba: str | None = None
    laqab: str | None = None
    birth_year_ah: int | None = None
    death_year_ah: int | None = None
    generation: str
    gender: str
    sect_affiliation: str
    trustworthiness_consensus: str
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
                    "grade_composite": "sahih",
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
    topic_tags: list[str] = []
    source_corpus: str
    collection_name: str | None = None
    display_title: str | None = None
    has_shia_parallel: bool = False
    has_sunni_parallel: bool = False


class HadithFacetsResponse(BaseModel):
    """Distinct facet values available for filtering hadiths."""

    model_config = ConfigDict(frozen=True)

    source_corpus: list[str]


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
    """A single search result."""

    model_config = ConfigDict(frozen=True)

    id: str
    type: str
    title: str
    title_ar: str
    score: float


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
    hadith_b_id: str
    hadith_b_corpus: str
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


# --- Admin models ---


class SystemHealthResponse(BaseModel):
    """System health response with per-service status."""

    model_config = ConfigDict(frozen=True)

    status: str
    neo4j: bool
    postgres: bool
    redis: bool


class ContentStatsResponse(BaseModel):
    """Content statistics for the admin dashboard."""

    model_config = ConfigDict(frozen=True)

    hadith_count: int
    narrator_count: int
    collection_count: int
    coverage_pct: float


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


class SystemConfigUpdate(BaseModel):
    """Partial update for system configuration."""

    rate_limit_per_minute: int | None = None
    cors_origins: list[str] | None = None
    feature_flags: dict[str, bool] | None = None
    max_search_results: int | None = None
    max_pagination_limit: int | None = None


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
