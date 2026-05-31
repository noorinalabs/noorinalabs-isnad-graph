"""Narrator node model for the isnad graph."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.enums import Gender, NarratorGeneration, SectAffiliation, TrustworthinessGrade

__all__ = ["Narrator"]


class Narrator(BaseModel):
    """A hadith narrator (rawi) in the isnad graph.

    Represents a historical person who participated in the transmission
    of prophetic traditions, with biographical metadata and graph metrics.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str
    """Canonical ID with 'nar:' prefix, e.g. 'nar:abu-hurayra-001'."""
    name_ar: str
    """Full Arabic name."""
    name_en: str
    """Full English transliteration."""
    name_ar_normalized: str | None = None
    """Pre-computed normalized form of ``name_ar`` for index/lookup matching."""
    kunya: str | None = None
    """Patronymic, e.g. 'Abu Hurayra'."""
    nisba: str | None = None
    """Geographic or tribal attribution, e.g. 'al-Dawsi'."""
    laqab: str | None = None
    """Honorific or epithet."""
    birth_year_ah: int | None = None
    """Birth year in Hijri calendar."""
    death_year_ah: int | None = None
    """Death year in Hijri calendar."""
    birth_location_id: str | None = None
    """FK to Location.id."""
    death_location_id: str | None = None
    """FK to Location.id."""
    generation: NarratorGeneration
    """Generation in the transmission chain (sahabi, tabii, etc.)."""
    gender: Gender
    """Biological gender."""
    sect_affiliation: SectAffiliation
    """Sectarian affiliation per biographical sources."""
    tabaqat_class: str | None = None
    """Layer/class in tabaqat literature."""
    trustworthiness_consensus: TrustworthinessGrade
    """Consensus trustworthiness grade from rijal criticism."""
    aliases: list[str] = Field(default_factory=list)
    """Alternate name forms for this narrator."""

    # Graph metrics (populated in Phase 4, nullable until then)
    betweenness_centrality: float | None = None
    in_degree: int | None = None
    out_degree: int | None = None
    pagerank: float | None = None
    community_id: int | None = None

    @field_validator("id")
    @classmethod
    def _validate_id_prefix(cls, v: str) -> str:
        if not v.startswith("nar:"):
            msg = f"Narrator id must start with 'nar:', got '{v}'"
            raise ValueError(msg)
        return v
