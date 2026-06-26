"""Narrator node model for the isnad graph."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.enums import (
    DatePrecision,
    Gender,
    NarratorGeneration,
    SectAffiliation,
    TrustworthinessGrade,
)

__all__ = ["Narrator", "NarratorDates"]


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
    """Birth year in Hijri calendar (point estimate / best single value)."""
    death_year_ah: int | None = None
    """Death year in Hijri calendar (point estimate / best single value)."""

    # Resolved date bounds + precision (additive; populated by the resolved-date
    # loader from the data-acquisition reconcile output, da#161-166). The point
    # estimates above stay for backward compatibility; these siblings model the
    # pervasive uncertainty in rijal dates. Death is the attested norm, birth the
    # exception — see _active_window in src/enrich/historical.py.
    birth_year_ah_earliest: int | None = None
    """Lower bound (inclusive) of the resolved birth year."""
    birth_year_ah_latest: int | None = None
    """Upper bound (inclusive) of the resolved birth year."""
    birth_year_ce: int | None = None
    """Birth year in the Common Era (computed once at resolve time)."""
    birth_date_precision: DatePrecision | None = None
    """How tightly the source dates the birth year."""
    death_year_ah_earliest: int | None = None
    """Lower bound (inclusive) of the resolved death year."""
    death_year_ah_latest: int | None = None
    """Upper bound (inclusive) of the resolved death year."""
    death_year_ce: int | None = None
    """Death year in the Common Era (computed once at resolve time)."""
    death_date_precision: DatePrecision | None = None
    """How tightly the source dates the death year."""
    floruit_year_ah: int | None = None
    """Tabaqa-derived 'active circa' midpoint when no year is attested."""
    region: str | None = None
    """Coarse geographic anchor (string; promote to a Location FK later)."""

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


class NarratorDates(BaseModel):
    """Resolved date record written onto an existing Narrator node.

    This is the focused loader-input contract for the resolved-date overlay
    (ig#1039): just the canonical id plus the date properties produced
    data-acquisition-side by the reconcile step (da#161-166). It is deliberately
    *not* the full :class:`Narrator` model — the loader only updates date
    properties on narrators that already exist in the graph, so the many
    required biographical fields would be noise here.

    All date fields are optional: a narrator may have a death year but no birth
    year (the common case), bounds but no point estimate, or nothing at all.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str
    """Canonical Narrator id (must start with 'nar:')."""
    birth_year_ah: int | None = None
    birth_year_ah_earliest: int | None = None
    birth_year_ah_latest: int | None = None
    birth_year_ce: int | None = None
    birth_date_precision: DatePrecision | None = None
    death_year_ah: int | None = None
    death_year_ah_earliest: int | None = None
    death_year_ah_latest: int | None = None
    death_year_ce: int | None = None
    death_date_precision: DatePrecision | None = None
    floruit_year_ah: int | None = None
    region: str | None = None

    @field_validator("id")
    @classmethod
    def _validate_id_prefix(cls, v: str) -> str:
        if not v.startswith("nar:"):
            msg = f"NarratorDates id must start with 'nar:', got '{v}'"
            raise ValueError(msg)
        return v
