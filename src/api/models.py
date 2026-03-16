"""API response models."""

from __future__ import annotations

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

    model_config = ConfigDict(frozen=True)

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

    model_config = ConfigDict(frozen=True)

    id: str
    matn_ar: str
    matn_en: str | None = None
    isnad_raw_ar: str | None = None
    isnad_raw_en: str | None = None
    grade_composite: str | None = None
    topic_tags: list[str] = []
    source_corpus: str
    has_shia_parallel: bool = False
    has_sunni_parallel: bool = False


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


class HealthResponse(BaseModel):
    """Health check response."""

    model_config = ConfigDict(frozen=True)

    status: str
    neo4j_connected: bool
